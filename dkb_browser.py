"""DKB-Wertpapierdokumente mit Browser-Login herunterladen.

Workaround fuer den Friendly-Captcha-Login (dkb-robo Issue #92): Es oeffnet
sich Microsoft Edge, du loggst dich dort normal ein (Captcha + App-Freigabe),
danach nutzt dkb-robo diese Browser-Sitzung. Nur EIN Login pro Lauf.

Ergebnis in <out_dir>:
  accounts_<zeit>.json        Konten-/Depotuebersicht
  depot_<nr>_<zeit>.json      aktuelle Depotpositionen (zum Abgleich in PP)
  dokumente/Wertpapierdokumente/<depot>/...pdf

Bereits vorhandene PDFs werden uebersprungen - nach einem Abbruch einfach
erneut starten. Dokumente werden in der Postbox NICHT als gelesen markiert.

Aufruf:  python dkb_browser.py [out_dir]

Baut auf dkb-robo (https://github.com/grindsa/dkb-robo, GPLv3) auf. Die Idee,
den Login per Playwright an einen echten Browser abzugeben, stammt von ThomFri
(https://github.com/grindsa/dkb-robo/issues/92).

SPDX-License-Identifier: GPL-3.0-or-later
"""

import datetime
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from dkb_robo import DKBRobo
from dkb_robo.authentication import Authentication, logger
from dkb_robo.portfolio import Overview
from dkb_robo.postbox import PostBox

LOGIN_TIMEOUT_S = 10 * 60
PROBE_URL = "https://banking.dkb.de/api/config/users/me/product-display-settings"
CATEGORY = "Wertpapierdokumente"
RETRY_WAITS_S = (5, 15, 30, 60)
PAUSE_BETWEEN_DOWNLOADS_S = 1.0


def log(msg):
    print(f">>> {msg}", file=sys.stderr, flush=True)


class ResponseWrapper:
    """Playwright-Response im Stil von requests.Response."""

    def __init__(self, resp):
        self._resp = resp
        self.status_code = resp.status
        self.headers = resp.headers

    @property
    def content(self):
        return self._resp.body()

    @property
    def text(self):
        return self._resp.text()

    def json(self):
        return self._resp.json()

    def raise_for_status(self):
        if not self._resp.ok:
            raise RuntimeError(f"HTTP {self._resp.status} fuer {self._resp.url}")


class ClientWrapper:
    """requests.Session-Ersatz auf Basis der Browser-Sitzung, mit Retry.

    Das DKB-Access-Token laeuft nach ca. 5 Minuten ab, ausserdem bricht die
    Bot-Abwehr gelegentlich Verbindungen ab. Bei Fehlern wird die Seite neu
    geladen (die DKB-Webapp erneuert dabei das Token) und erneut versucht.
    """

    def __init__(self, context, page):
        self._context = context
        self._page = page
        self._api = context.request

    def _xsrf(self):
        for cookie in self._context.cookies("https://banking.dkb.de"):
            if cookie["name"] == "__Host-xsrf":
                return cookie["value"]
        return None

    def _raw(self, method, url, headers, data):
        if method != "get":
            token = self._xsrf()
            if token:
                headers.setdefault("x-xsrf-token", token)
        params = {"headers": headers}
        if data is not None:
            params["data"] = data
        return ResponseWrapper(getattr(self._api, method)(url, **params))

    def session_ok(self):
        try:
            return self._raw("get", PROBE_URL, {}, None).status_code == 200
        except Exception:  # noqa: BLE001
            return False

    def refresh(self):
        """Seite neu laden, damit die Webapp das Token erneuert."""
        try:
            self._page.reload(wait_until="networkidle", timeout=60_000)
        except Exception:  # noqa: BLE001
            pass
        for _ in range(20):
            if self.session_ok():
                return True
            self._page.wait_for_timeout(3000)
        return False

    def _call(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", None) or {})
        data = kwargs.pop("data", None)
        if "json" in kwargs:
            data = json.dumps(kwargs.pop("json"))

        last_err = None
        for attempt, wait in enumerate((0,) + RETRY_WAITS_S):
            if wait:
                log(f"Fehler ({last_err}) - Versuch {attempt + 1}, warte {wait}s und erneuere Sitzung ...")
                time.sleep(wait)
                if not self.refresh():
                    log("Sitzung ungueltig - ggf. im Edge-Fenster erneut einloggen.")
            try:
                resp = self._raw(method, url, dict(headers), data)
            except Exception as err:  # noqa: BLE001  (z.B. ECONNRESET)
                last_err = str(err).splitlines()[0]
                continue
            if resp.status_code in (401, 403) or resp.status_code >= 500:
                last_err = f"HTTP {resp.status_code}"
                continue
            return resp
        raise RuntimeError(f"{method.upper()} {url} endgueltig fehlgeschlagen: {last_err}")

    def get(self, url, **kwargs):
        return self._call("get", url, **kwargs)

    def post(self, url, **kwargs):
        return self._call("post", url, **kwargs)

    def patch(self, url, **kwargs):
        return self._call("patch", url, **kwargs)


def browser_login(self):
    """Ersetzt Authentication.login(): Login passiert im echten Browser."""
    logger.debug("browser_login()\n")
    self._pw = sync_playwright().start()
    self._browser = self._pw.chromium.launch(channel="msedge", headless=False)
    context = self._browser.new_context()
    page = context.new_page()
    page.goto("https://banking.dkb.de/login")
    self.client = ClientWrapper(context, page)

    log("Bitte im Edge-Fenster bei DKB einloggen (Captcha, Freigabe in der DKB-App).")
    log("Fenster danach offen lassen - es geht automatisch weiter.")
    deadline = time.time() + LOGIN_TIMEOUT_S
    while not self.client.session_ok():
        if time.time() > deadline:
            raise RuntimeError("Login nicht innerhalb von 10 Minuten abgeschlossen")
        page.wait_for_timeout(3000)
    log("Login erkannt.")

    self.account_dic = Overview(client=self.client, unfiltered=self.unfiltered).get()
    return self.account_dic, None


def browser_logout(self):
    for obj, meth in (("_browser", "close"), ("_pw", "stop")):
        try:
            getattr(getattr(self, obj), meth)()
        except Exception:  # noqa: BLE001
            pass


Authentication.login = browser_login
Authentication.logout = browser_logout


def main(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    doc_dir = out_dir / "dokumente"

    with DKBRobo(dkb_user="browser", dkb_password="unused") as dkb:
        client = dkb.wrapper.client

        # 1) Uebersicht + Depotpositionen
        (out_dir / f"accounts_{stamp}.json").write_text(
            json.dumps(dkb.account_dic, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        for acc in dkb.account_dic.values():
            if acc.get("type") == "depot":
                try:
                    today = datetime.date.today().strftime("%d.%m.%Y")
                    positions = dkb.get_transactions(acc["transactions"], "depot", today, today)
                    name = acc.get("account") or acc.get("id")
                    (out_dir / f"depot_{name}_{stamp}.json").write_text(
                        json.dumps(positions, indent=2, ensure_ascii=False, default=str),
                        encoding="utf-8",
                    )
                    log(f"Depot {name}: {len(positions)} Positionen gespeichert.")
                except Exception as err:  # noqa: BLE001
                    log(f"Depotpositionen konnten nicht geladen werden: {err}")

        # 2) Nur Wertpapierdokumente aus der Postbox
        items = PostBox(client=client).fetch_items()
        docs = [d for d in items.values() if d.message and d.category() == CATEGORY]
        log(f"{len(docs)} Wertpapierdokumente gefunden (von {len(items)} Dokumenten insgesamt).")

        accounts_by_id = dkb._accounts_by_id()  # pylint: disable=w0212
        done = skipped = failed = 0
        for i, doc in enumerate(docs, 1):
            target = doc_dir / CATEGORY / str(doc.account(card_lookup=accounts_by_id))
            target_file = target / f"{doc.date()}_{doc.filename()}"
            if target_file.exists():
                skipped += 1
                continue
            log(f"[{i}/{len(docs)}] {doc.subject()}")
            try:
                doc.download(client, target_file)
                done += 1
                time.sleep(PAUSE_BETWEEN_DOWNLOADS_S)
            except Exception as err:  # noqa: BLE001
                failed += 1
                log(f"  FEHLER: {err}")

        log(f"Fertig: {done} neu, {skipped} schon vorhanden, {failed} fehlgeschlagen.")
        if failed:
            log("Fuer die fehlgeschlagenen Dokumente das Skript einfach erneut starten.")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "downloads")

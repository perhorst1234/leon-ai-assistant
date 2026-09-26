"""Durable marketplace watches and asynchronous read-only search runs."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
import time
import urllib.request
import uuid

from leon_control_plane.marketplace_browser_mcp import BrowserBridge
from leon_control_plane.secret_scanner import assert_no_secrets

ROOT = Path(__file__).resolve().parents[2]
WEEK = 7 * 86400


def browser_bridge() -> BrowserBridge:
    for package in sorted((Path.home() / ".npm/_npx").glob("*/node_modules/agent-browser/package.json")):
        if json.loads(package.read_text()).get("version") == "0.27.0":
            return BrowserBridge(package.parent / "bin/agent-browser.js", "http://127.0.0.1:9223",
                                 Path.home() / ".local/state/leon/marketplace-audit.jsonl", allow_messages=True)
    raise RuntimeError("browser_cli_unavailable")


def ram_capacity(text: str) -> int | None:
    """Capacity evidence only; never multiply price by an inferred stick count."""
    bundles = [int(a) * int(b) for a, b in re.findall(r"\b(\d{1,2})\s*[x×]\s*(\d{1,3})\s*g[bB]\b", text, re.I)]
    amounts = [int(value) for value in re.findall(r"\b(\d{1,3})\s*gb\b", text, re.I)]
    return max(bundles + amounts, default=0) or None


def shortlist(items: list[dict], watch: dict) -> list[dict]:
    selected = []
    seen = set()
    terms = watch["required_terms"]
    excluded = watch["excluded_terms"]
    for item in items:
        text = f"{item['title']} {item['text']}".casefold()
        if item["url"] in seen or any(term.casefold() not in text for term in terms) or any(term.casefold() in text for term in excluded):
            continue
        seen.add(item["url"])
        capacity = (ram_capacity(item["title"]) or ram_capacity(item["text"])) if watch["min_ram_gb"] else None
        if watch["min_ram_gb"] and any(term in text for term in ("gezocht:", "wij kopen", "gereserveerd")):
            continue
        if watch["min_ram_gb"] and (capacity is None or capacity < watch["min_ram_gb"]):
            continue
        bundle = re.search(r"\b(\d{1,2})\s*[x×]\s*(\d{1,3})\s*gb\b", item["title"], re.I)
        usable = min(int(bundle[1]), watch.get("max_ram_sticks", 0) or int(bundle[1])) * int(bundle[2]) if bundle else capacity
        if watch["min_ram_gb"] and usable is not None and usable < watch["min_ram_gb"]:
            continue
        match = re.search(r"€\s*([0-9][0-9.]*(?:,[0-9]{2})?)", item["text"])
        price = round(float(match[1].replace(".", "").replace(",", ".")) * 100) if match else None
        # A small above-budget asking price may be negotiable; it is never a
        # claim that the seller accepts the owner's budget.
        if price is not None and price > watch["max_total_cents"] * 1.25:
            continue
        notes = ["Verzending en totaalprijs nog bevestigen"]
        if capacity:
            notes.append(f"Advertentie noemt {capacity} GB; setomvang en prijs voor de hele set controleren")
        if capacity and usable != capacity:
            notes.append(f"Met {watch['max_ram_sticks']} slots is {usable} GB van deze set bruikbaar")
        if "lrdimm" in text:
            notes.append("LRDIMM: controleer moederbordcompatibiliteit")
        elif "rdimm" in text or "registered" in text:
            notes.append("RDIMM: controleer moederbordcompatibiliteit")
        elif "ecc" in text:
            notes.append("ECC-type nog controleren")
        if price is None:
            notes.append("Geen vaste vraagprijs; prijs navragen")
        elif price > watch["max_total_cents"]:
            notes.append("Vraagprijs boven budget; onderhandeling nodig")
        selected.append({"url": item["url"], "title": item["title"], "asking_price_cents": price,
                         "capacity_gb": capacity, "usable_capacity_gb": usable, "notes": notes, "total_price_confirmed": False})
    return sorted(selected, key=lambda item: (
        0 if (item["usable_capacity_gb"] or 0) >= watch["preferred_ram_gb"] > 0 else 1,
        item["asking_price_cents"] is None, item["asking_price_cents"] or 0, item["url"],
    ))[:12]


class ShopperService:
    def __init__(self, path: Path, *, bridge_factory=browser_bridge, clock=time.time):
        self.path, self.bridge_factory, self.clock = path, bridge_factory, clock
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as connection:
            connection.executescript('''
                CREATE TABLE IF NOT EXISTS watches (
                    id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, spec TEXT NOT NULL,
                    enabled INTEGER NOT NULL, next_run REAL NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, watch_id TEXT NOT NULL, status TEXT NOT NULL,
                    started_at REAL NOT NULL, finished_at REAL, result TEXT);
                CREATE INDEX IF NOT EXISTS runs_watch ON runs(watch_id, started_at DESC);
                CREATE TABLE IF NOT EXISTS contacts (
                    url TEXT PRIMARY KEY, watch_id TEXT NOT NULL, attempted_at REAL NOT NULL,
                    status TEXT NOT NULL, result TEXT);
                CREATE TABLE IF NOT EXISTS replies (
                    fingerprint TEXT PRIMARY KEY, contact_url TEXT NOT NULL, conversation_url TEXT NOT NULL,
                    received_at REAL NOT NULL, due_at REAL NOT NULL, status TEXT NOT NULL,
                    seller_text TEXT NOT NULL, result TEXT);
            ''')
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @contextmanager
    def browser_lock(self):
        # Shared across the API process and the timer so a search cannot switch
        # conversations during another shopper browser operation.
        path = self.path.parent / "shopper-browser.lock"
        with path.open("a") as handle:
            path.chmod(0o600)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("browser_busy") from None
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def create(self, body: dict) -> dict:
        allowed = {"request_id", "platform", "query", "max_total_cents", "min_ram_gb", "preferred_ram_gb", "max_ram_sticks", "automatic_messages", "required_terms", "excluded_terms"}
        if not isinstance(body, dict) or set(body) - allowed:
            raise ValueError("Invalid watch fields")
        try:
            request_id = str(uuid.UUID(body["request_id"]))
        except (KeyError, ValueError, TypeError, AttributeError):
            raise ValueError("request_id must be a UUID") from None
        platform, query = body.get("platform"), body.get("query")
        if platform not in {"marktplaats", "vinted", "both"} or not isinstance(query, str) or not 1 <= len(query.strip()) <= 160:
            raise ValueError("Choose Marktplaats/Vinted and a query of 1–160 characters")
        budget = body.get("max_total_cents")
        if type(budget) is not int or not 1 <= budget <= 1_000_000:
            raise ValueError("Set a maximum total price in cents")
        spec = {"platform": platform, "query": query.strip(), "max_total_cents": budget}
        automatic_messages = body.get("automatic_messages", False)
        if type(automatic_messages) is not bool or (automatic_messages and platform not in {"marktplaats", "both"}):
            raise ValueError("Automatic contact currently supports Marktplaats only")
        spec["automatic_messages"] = automatic_messages
        for field in ("min_ram_gb", "preferred_ram_gb", "max_ram_sticks"):
            value = body.get(field, 0)
            if type(value) is not int or not 0 <= value <= (32 if field == "max_ram_sticks" else 1024):
                raise ValueError("Invalid RAM capacity")
            spec[field] = value
        for field in ("required_terms", "excluded_terms"):
            values = body.get(field, [])
            if not isinstance(values, list) or len(values) > 8 or any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 40 for v in values):
                raise ValueError("Invalid search terms")
            spec[field] = [value.strip() for value in values]
        assert_no_secrets("shopper watch", spec)
        encoded = json.dumps(spec, sort_keys=True)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM watches WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["spec"] != encoded:
                    raise ValueError("request_id is bound to a different watch")
                return {"id": existing["id"], **spec}
            if connection.execute("SELECT COUNT(*) FROM watches WHERE enabled=1").fetchone()[0] >= 8:
                raise ValueError("Maximum eight active watches")
            watch_id = "watch-" + uuid.uuid4().hex
            connection.execute("INSERT INTO watches VALUES(?,?,?,?,?,?)", (watch_id, request_id, encoded, 1, self.clock(), self.clock()))
        return {"id": watch_id, **spec}

    def state(self) -> dict:
        now = self.clock()
        with self.connect() as connection:
            watches = []
            for row in connection.execute("SELECT * FROM watches ORDER BY created_at DESC LIMIT 24"):
                latest = connection.execute("SELECT * FROM runs WHERE watch_id=? ORDER BY started_at DESC LIMIT 1", (row["id"],)).fetchone()
                run = dict(latest) if latest else None
                if run:
                    run["result"] = json.loads(run["result"]) if run["result"] else None
                replies = [dict(item) for item in connection.execute(
                    "SELECT replies.status,replies.due_at,replies.conversation_url FROM replies JOIN contacts ON contacts.url=replies.contact_url WHERE contacts.watch_id=? ORDER BY replies.received_at DESC LIMIT 8", (row["id"],))]
                watches.append({"id": row["id"], **json.loads(row["spec"]), "enabled": bool(row["enabled"]), "next_run": row["next_run"], "latest_run": run, "replies": replies, "held_contacts": connection.execute("SELECT COUNT(*) FROM contacts WHERE watch_id=? AND status='on_hold'", (row["id"],)).fetchone()[0]})
        try:
            with urllib.request.urlopen("http://127.0.0.1:9223/json/version", timeout=1) as response:
                connected = response.status == 200
        except Exception:
            connected = False
        return {"ok": True, "browser_connected": connected, "watches": watches, "weekly_interval_seconds": WEEK,
                "messages_enabled": True, "purchases_enabled": False, "reply_window": {"timezone": "Europe/Amsterdam", "start_hour": 8, "latest_hour": 23, "delay_minutes_min": 15, "delay_minutes_max": 45, "trigger": "browser_dom_events"}, "now": now}

    def set_enabled(self, watch_id: str, enabled: bool) -> dict:
        if not isinstance(watch_id, str) or type(enabled) is not bool:
            raise ValueError("Expected watch id and enabled boolean")
        with self.connect() as connection:
            if connection.execute("UPDATE watches SET enabled=? WHERE id=?", (int(enabled), watch_id)).rowcount != 1:
                raise ValueError("Unknown watch")
        return {"ok": True}

    def start(self, watch_id: str, *, background: bool = True, due_only: bool = False) -> dict:
        now = self.clock()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
            if row is None or not row["enabled"]:
                raise ValueError("Watch missing or disabled")
            if due_only and row["next_run"] > now:
                return {"ok": True, "status": "not_due"}
            active = connection.execute("SELECT * FROM runs WHERE watch_id=? AND status='running' ORDER BY started_at DESC LIMIT 1", (watch_id,)).fetchone()
            if active and now - active["started_at"] < 300:
                return {"ok": True, "run_id": active["id"], "status": "running"}
            if active:
                connection.execute("UPDATE runs SET status='interrupted', finished_at=? WHERE id=?", (now, active["id"]))
            latest = connection.execute("SELECT MAX(started_at) FROM runs WHERE watch_id=?", (watch_id,)).fetchone()[0]
            if latest and now - latest < 60:
                raise ValueError("Wait one minute before searching this watch again")
            run_id = "shopper-run-" + uuid.uuid4().hex
            connection.execute("INSERT INTO runs VALUES(?,?,?,?,?,?)", (run_id, watch_id, "running", now, None, None))
            connection.execute("UPDATE watches SET next_run=? WHERE id=?", (now + WEEK, watch_id))
            spec = json.loads(row["spec"])
        if background:
            threading.Thread(target=self.execute, args=(run_id, watch_id, spec), daemon=True).start()
        else:
            self.execute(run_id, watch_id, spec)
        return {"ok": True, "run_id": run_id, "status": "running" if background else "finished"}

    def execute(self, run_id: str, watch_id: str, spec: dict) -> None:
        platforms = ['marktplaats', 'vinted'] if spec['platform']=='both' else [spec['platform']]
        sources, items = [], []
        effective = dict(spec)
        if self.clock() >= spec.get('fallback_after', float('inf')):
            effective['min_ram_gb'] = spec.get('fallback_min_ram_gb', spec['min_ram_gb'])
        for platform in platforms:
            try:
                with self.browser_lock():
                    page = self.bridge_factory().search(platform, spec['query'])
                if page['challenge']:
                    sources.append({'platform': platform, 'status': 'needs_owner', 'checked': 0, 'reason': 'Website vraagt een menselijke controle'})
                elif not page['items'] and not page['empty']:
                    sources.append({'platform': platform, 'status': 'needs_owner', 'checked': 0, 'reason': 'Toestemming of login nodig'})
                else:
                    sources.append({'platform': platform, 'status': 'complete', 'checked': len(page['items'])})
                    items.extend({**item, 'platform': platform} for item in page['items'])
            except Exception:
                sources.append({'platform': platform, 'status': 'disconnected', 'checked': 0, 'reason': 'Serverbrowser of website niet beschikbaar'})
        matches = shortlist(items, effective)
        by_url = {item['url']: item['platform'] for item in items}
        for match in matches:
            match['platform'] = by_url[match['url']]
        complete = sum(source['status']=='complete' for source in sources)
        status = 'complete' if complete==len(sources) else 'partial' if complete else sources[0]['status']
        result = {'matches': matches, 'sources': sources, 'listings_checked': sum(source['checked'] for source in sources),
                  'source': spec['platform'], 'scope': 'First 40 rendered listings per source; asking prices, not confirmed totals'}
        if not complete:
            result['reason'] = 'Controleer de serverbrowserverbinding of website-login.'
        contacts = [match for match in matches if match['platform']=='marktplaats']
        if spec.get('automatic_messages') and contacts:
            result['agent'] = self.autonomous_contact(watch_id, effective, contacts)
        with self.connect() as connection:
            connection.execute('UPDATE runs SET status=?,finished_at=?,result=? WHERE id=?', (status, self.clock(), json.dumps(result), run_id))
            if status not in {'complete', 'partial'}:
                connection.execute('UPDATE watches SET next_run=? WHERE id=?', (self.clock()+3600, watch_id))

    def edit(self, watch_id: str, changes: dict) -> None:
        allowed = {'query','max_total_cents','min_ram_gb','preferred_ram_gb','max_ram_sticks','wait_days','platform'}
        if not changes or set(changes)-allowed:
            raise ValueError('Unsupported watch changes')
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT spec FROM watches WHERE id=?',(watch_id,)).fetchone()
            if not row:
                raise ValueError('Unknown watch')
            spec = json.loads(row['spec'])
            for key,value in changes.items():
                if key=='query' and (not isinstance(value,str) or not 1<=len(value.strip())<=160):
                    raise ValueError('Invalid query')
                if key=='platform' and value not in {'marktplaats','vinted','both'}:
                    raise ValueError('Invalid platforms')
                if key not in {'query','platform'}:
                    maximum = 1000000 if key=='max_total_cents' else 32 if key=='max_ram_sticks' else 90 if key=='wait_days' else 1024
                    if type(value) is not int or not 0<=value<=maximum or (key=='max_total_cents' and value==0):
                        raise ValueError('Invalid watch limit')
                if key=='wait_days':
                    spec['fallback_after'] = self.clock()+value*86400
                else:
                    spec[key] = value.strip() if isinstance(value,str) else value
            if 'query' in changes:
                ddr3 = 'ddr3' in spec['query'].casefold()
                spec['required_terms'] = ['ddr3'] if ddr3 else []
                spec['excluded_terms'] = ['ddr4', 'sodimm', 'so-dimm', 'gezocht'] if ddr3 else []
            c.execute('UPDATE watches SET spec=? WHERE id=?',(json.dumps(spec,sort_keys=True),watch_id))

    def hold(self, watch_id: str) -> None:
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            latest = c.execute('SELECT url FROM contacts WHERE watch_id=? ORDER BY attempted_at DESC LIMIT 1',(watch_id,)).fetchone()
            if not latest:
                raise ValueError('No seller contact to hold')
            c.execute("UPDATE contacts SET status='on_hold' WHERE url=?",(latest['url'],))
            c.execute("UPDATE replies SET status='on_hold' WHERE contact_url=? AND status='pending'",(latest['url'],))

    def autonomous_contact(self, watch_id: str, spec: dict, matches: list[dict]) -> dict:
        from leon_control_plane.shopper_runtime import contact_decision, contact_message, send_first_contact
        try:
            with self.connect() as connection:
                previous = {row[0] for row in connection.execute("SELECT url FROM contacts")}
                daily = connection.execute("SELECT COUNT(*) FROM contacts WHERE attempted_at>?", (self.clock() - 86400,)).fetchone()[0]
            candidates = [item for item in matches if item["url"] not in previous]
            if not candidates or daily >= 2:
                return {"status": "waiting", "reason": "Previously contacted or daily contact limit reached"}
            decision = contact_decision(spec, candidates)
            if decision["candidate_index"] is None:
                return {"status": "waiting", "reason": "Local shopper found no suitable contact"}
            candidate = candidates[decision["candidate_index"]]
            message = contact_message(spec, candidate, decision["offer_cents"])
            with self.browser_lock(), self.connect() as connection:
                # Claim before any external action; a crash cannot repeat contact.
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT COUNT(*) FROM contacts WHERE attempted_at>?", (self.clock() - 86400,)).fetchone()[0] >= 2:
                    return {"status": "waiting", "reason": "Daily contact limit reached"}
                connection.execute("INSERT INTO contacts VALUES(?,?,?,?,?)", (candidate["url"], watch_id, self.clock(), "attempted", None))
            with self.browser_lock():
                outcome = send_first_contact(self.bridge_factory(), candidate["url"], message)
            with self.connect() as connection:
                connection.execute("UPDATE contacts SET status=?,result=? WHERE url=?", (outcome["status"], json.dumps(outcome), candidate["url"]))
            return {"status": outcome["status"], "listing_url": candidate["url"], "offer_cents": decision["offer_cents"],
                    "model": decision["model"], "reason": outcome.get("reason", decision["reason"]),
                    "conversation_url": outcome.get("conversation_url")}
        except Exception as exc:
            return {"status": "needs_owner", "reason": "Local shopper model or messaging interface unavailable; no automatic retry", "error_code": type(exc).__name__}

    def follow_up(self, *, due_only: bool = False) -> None:
        """Observe only our confirmed contacts; persist delay before answering."""
        from leon_control_plane.shopper_runtime import read_conversation, reply_decision, send_reply
        from leon_control_plane.shopper_schedule import reply_due, AMSTERDAM
        from datetime import datetime
        from leon_control_plane.shopper_runtime import confirm_delivery
        with self.connect() as c:
            uncertain = c.execute("SELECT contacts.* FROM contacts JOIN watches ON watches.id=contacts.watch_id WHERE watches.enabled=1 AND contacts.status IN ('clicked','unknown') LIMIT 8").fetchall()
        for contact in uncertain:
            previous = json.loads(contact["result"] or '{}')
            if not previous.get("listing_title") or not previous.get("message_hash"):
                continue
            try:
                with self.browser_lock():
                    checked = confirm_delivery(self.bridge_factory(), previous["listing_title"], previous["message_hash"])
                with self.connect() as c:
                    c.execute("UPDATE contacts SET status=?,result=? WHERE url=?", (checked["status"], json.dumps({**previous, **checked}), contact["url"]))
            except Exception:
                pass
        with self.connect() as c:
            query = "SELECT contacts.*,watches.spec FROM contacts JOIN watches ON watches.id=contacts.watch_id WHERE watches.enabled=1 AND contacts.status='confirmed'"
            if due_only:
                query += " AND EXISTS(SELECT 1 FROM replies WHERE replies.contact_url=contacts.url AND replies.status='pending' AND replies.due_at<=?)"
            contacts = c.execute(query + " LIMIT 8", (self.clock(),) if due_only else ()).fetchall()
        for contact in contacts:
            spec = json.loads(contact["spec"])
            if not spec.get("automatic_messages"):
                continue
            url = json.loads(contact["result"] or '{}').get("conversation_url")
            if not url or "/messages/" not in url:
                continue
            try:
                with self.browser_lock():
                    bridge = self.bridge_factory()
                    rows = read_conversation(bridge, url)
                if not rows or rows[-1]["own"]:
                    with self.connect() as c:
                        c.execute("UPDATE replies SET status='superseded' WHERE contact_url=? AND status='pending'", (contact["url"],))
                    continue
                # Only a seller turn following a known owner message qualifies.
                owner_indexes = [i for i, row in enumerate(rows) if row["own"]]
                if not owner_indexes:
                    continue
                incoming = rows[owner_indexes[-1] + 1:]
                seller_text = "\n".join(row["text"] for row in incoming)[-1200:]
                fingerprint = hashlib.sha256((url + json.dumps(rows, sort_keys=True)).encode()).hexdigest()
                now = self.clock()
                with self.connect() as c:
                    c.execute("BEGIN IMMEDIATE")
                    c.execute("UPDATE replies SET status='superseded' WHERE contact_url=? AND fingerprint<>? AND status='pending'", (contact["url"], fingerprint))
                    c.execute("INSERT OR IGNORE INTO replies VALUES(?,?,?,?,?,'pending',?,NULL)", (fingerprint, contact["url"], url, now, reply_due(now, fingerprint), seller_text))
                    event = c.execute("SELECT * FROM replies WHERE fingerprint=?", (fingerprint,)).fetchone()
                if event["status"] != 'pending' or event["due_at"] > now:
                    continue
                local = datetime.fromtimestamp(now, AMSTERDAM)
                if not 8 <= local.hour < 23:
                    with self.connect() as c:
                        c.execute("UPDATE replies SET due_at=? WHERE fingerprint=? AND status='pending'", (reply_due(now, fingerprint), fingerprint))
                    continue
                decision = reply_decision(spec, seller_text)
                with self.browser_lock():
                    bridge = self.bridge_factory()
                    fresh = read_conversation(bridge, url)
                    if fresh != rows:
                        # A seller or owner update invalidates the decision.
                        continue
                    with self.connect() as c:
                        c.execute("BEGIN IMMEDIATE")
                        claimed = c.execute("UPDATE replies SET status='attempted' WHERE fingerprint=? AND status='pending'", (fingerprint,)).rowcount
                    if not claimed:
                        continue
                    if decision["action"] == 'ready':
                        outcome = {"status": "ready_for_owner", "purchase_confirmed": False, "model": decision["model"]}
                    else:
                        outcome = {**send_reply(bridge, url, decision["message"]), "model": decision["model"], "action": decision["action"]}
                    with self.connect() as c:
                        c.execute("UPDATE replies SET status=?,result=? WHERE fingerprint=?", (outcome["status"], json.dumps(outcome), fingerprint))
            except Exception:
                # A pending decision may be recomputed next poll. An attempted
                # external send is never repeated, including after a restart.
                continue


_service = None
_service_lock = threading.Lock()


def shopper_request(method: str, path: str, body=None):
    global _service
    if not path.startswith("/api/shopper/"):
        return None
    with _service_lock:
        if _service is None:
            _service = ShopperService(ROOT / ".runtime/shopper.sqlite")
    if method == "GET" and path == "/api/shopper/state":
        return _service.state()
    if method == "POST" and path == "/api/shopper/watches":
        return {"ok": True, "watch": _service.create(body)}
    if method == "POST" and path == "/api/shopper/run" and isinstance(body, dict) and set(body) == {"watch_id"}:
        return _service.start(body["watch_id"])
    if method == "POST" and path == "/api/shopper/control" and isinstance(body, dict) and set(body) == {"watch_id", "enabled"}:
        return _service.set_enabled(body["watch_id"], body["enabled"])
    raise ValueError("Unknown shopper action")


def main():
    parser = argparse.ArgumentParser(description="Run due marketplace searches and delayed replies")
    parser.add_argument("--db", type=Path, default=ROOT / ".runtime/shopper.sqlite")
    parser.add_argument("--follow-up-only", action="store_true")
    parser.add_argument("--due-replies-only", action="store_true")
    args = parser.parse_args()
    service = ShopperService(args.db)
    with service.connect() as connection:
        ids = [row[0] for row in connection.execute("SELECT id FROM watches WHERE enabled=1 AND next_run<=? LIMIT 8", (service.clock(),))]
    if args.follow_up_only:
        service.follow_up(due_only=args.due_replies_only)
        with service.connect() as c:
            due = c.execute("SELECT MIN(due_at) FROM replies WHERE status='pending'").fetchone()[0]
        print(json.dumps({"next_reply_due": due}))
        return
    for watch_id in ids:
        service.start(watch_id, background=False, due_only=True)


if __name__ == "__main__":
    main()

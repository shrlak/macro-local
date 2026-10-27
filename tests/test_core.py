import json, os, sys, tempfile, threading, unittest, urllib.request
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["MACRO_HOME"] = tempfile.mkdtemp()
import ics, mailer  # noqa: E402

ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
UID:a1@x\r
SUMMARY:Standup\\, daily\r
DTSTART;TZID=America/New_York:20261026T090000\r
DTEND;TZID=America/New_York:20261026T093000\r
RRULE:FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4\r
DESCRIPTION:line one\\nline\r
  two\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:b2@x\r
SUMMARY:Retreat\r
DTSTART;VALUE=DATE:20261101\r
DTEND;VALUE=DATE:20261103\r
END:VEVENT\r
END:VCALENDAR\r
"""


class IcsTests(unittest.TestCase):
    def test_parse(self):
        ev = ics.parse_ics(ICS)
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[0]["title"], "Standup, daily")
        self.assertEqual(ev[0]["body"], "line one\nline two")
        if ics.ZoneInfo:
            self.assertEqual(ev[0]["start"], "2026-10-26T09:00")  # recurring: wall-clock kept (DST-safe)
        self.assertEqual((ev[1]["start"], ev[1]["end"], ev[1]["allday"]), ("2026-11-01", "2026-11-02", "yes"))

    def test_weekly_byday_count(self):
        occ = list(ics.occurrences("2026-10-26T09:00", "2026-10-26T09:30", "FREQ=WEEKLY;BYDAY=MO,WE;COUNT=4", "2026-10-01", "2026-12-31"))
        self.assertEqual([o[0][:10] for o in occ], ["2026-10-26", "2026-10-28", "2026-11-02", "2026-11-04"])

    def test_window_and_monthly(self):
        occ = list(ics.occurrences("2026-01-31T10:00", "2026-01-31T11:00", "FREQ=MONTHLY", "2026-02-01", "2026-03-31"))
        self.assertEqual([o[0][:10] for o in occ], ["2026-02-28", "2026-03-31"])
        self.assertEqual(list(ics.occurrences("2026-05-01T10:00", None, "", "2026-06-01", "2026-06-30")), [])

    def test_allday_multiday_overlap(self):
        self.assertTrue(list(ics.occurrences("2026-11-01", "2026-11-03", "", "2026-11-03", "2026-11-03")))
        self.assertFalse(list(ics.occurrences("2026-11-01", "2026-11-03", "", "2026-11-04", "2026-11-04")))

    def test_export_roundtrip(self):
        evs = [{"id": "i", "title": "A; B", "body": "x\ny", "data": {"start": "2026-11-01", "end": "2026-11-02", "allday": "yes", "uid": "u1"}},
               {"id": "j", "title": "T", "body": "", "data": {"start": "2026-11-01T10:00Z", "end": "2026-11-01T11:00Z", "rrule": "FREQ=DAILY"}}]
        back = ics.parse_ics(ics.export_ics(evs))
        self.assertEqual([(e["title"], e["start"], e["end"]) for e in back],
                         [("A; B", "2026-11-01", "2026-11-02"), ("T", "2026-11-01T10:00Z", "2026-11-01T11:00Z")])
        self.assertEqual(back[1]["rrule"], "FREQ=DAILY")


def raw_mail():
    m = EmailMessage()
    m["From"], m["To"] = "=?utf-8?q?Zo=C3=AB?= <zoe@acme.com>", "me@x.com"
    m["Subject"], m["Message-ID"] = "Quarterly plan", "<m1@acme.com>"
    m["Date"] = "Mon, 26 Oct 2026 10:00:00 +0000"
    m.set_content("plain body")
    m.add_alternative("<p>html body</p>", subtype="html")
    m.add_attachment(b"data", maintype="application", subtype="pdf", filename="plan.pdf")
    return m.as_bytes()


class FakeIMAP:
    def __init__(self, uids): self.uids, self.fetched = uids, []
    def login(self, u, p): self.creds = (u, p)
    def select(self, box, readonly=False): assert readonly; return "OK", [b"3"]
    def uid(self, cmd, *a):
        if cmd == "SEARCH":
            return "OK", [b" ".join(str(u).encode() for u in self.uids)]
        self.fetched.append(a[0])
        return "OK", [(b"1 (UID %s)" % a[0].encode(), raw_mail()), b")"]
    def logout(self): pass


class MailTests(unittest.TestCase):
    def test_parse(self):
        m = mailer.parse_message(raw_mail())
        self.assertEqual(m["subject"], "Quarterly plan")
        self.assertIn("Zoë", m["from"])
        self.assertEqual(m["body"], "plain body")
        self.assertEqual(m["attachments"], ["plan.pdf"])

    def test_fetch_only_new(self):
        f = FakeIMAP([1, 2, 3, 4])
        out, newest = mailer.fetch_new({"username": "u", "address": "a", "password": "p"}, last_uid=2, connect=lambda: f)
        self.assertEqual([u for u, _ in out], [3, 4])
        self.assertEqual(newest, 4)
        out, newest = mailer.fetch_new({"username": "u", "address": "a", "password": "p"}, last_uid=4, connect=lambda: FakeIMAP([4]))
        self.assertEqual((out, newest), ([], 4))

    def test_html_only(self):
        self.assertEqual(mailer.html_to_text("<style>x{}</style><p>Hi &amp; bye</p><br>there"), "Hi & bye\n\nthere")

    def test_send(self):
        sent = {}
        class S:
            def __init__(s, host, port, **kw): sent["host"] = (host, port)
            def starttls(s, context=None): sent["tls"] = True
            def login(s, u, p): sent["login"] = u
            def send_message(s, m, to_addrs): sent["msg"], sent["to"] = m, to_addrs
            def quit(s): pass
        cfg = {"address": "me@x.com", "name": "Me", "username": "me@x.com", "password": "p", "smtp_host": "smtp.x.com", "smtp_port": 587}
        mailer.send(cfg, "A <a@y.com>, b@y.com", "Re: hi", "body", cc="c@y.com", in_reply_to="<m1@acme.com>", smtp_plain=S)
        self.assertTrue(sent["tls"])
        self.assertEqual(sent["to"], ["a@y.com", "b@y.com", "c@y.com"])
        self.assertEqual(sent["msg"]["In-Reply-To"], "<m1@acme.com>")
        self.assertEqual(sent["msg"]["From"], "Me <me@x.com>")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = server
        cls.srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.srv.daemon_threads = True
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}/api"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.srv.shutdown()

    def call(self, method, path, body=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        r = urllib.request.urlopen(urllib.request.Request(self.base + path, data=data, method=method, headers={"Content-Type": "application/json"}))
        t = r.read()
        return json.loads(t) if r.headers["Content-Type"].startswith("application/json") else t.decode()

    def test_calendar_import_window_export(self):
        import server
        with server.lock:
            server.db.execute("DELETE FROM items WHERE type='event'"); server.db.commit()
        self.assertEqual(self.call("POST", "/calendar/import", {"ics": ICS})["imported"], 2)
        self.call("POST", "/calendar/import", {"ics": ICS})  # idempotent (upsert by uid)
        self.assertEqual(len(self.call("GET", "/items?type=event")), 2)
        w = self.call("GET", "/calendar?start=2026-11-01&end=2026-11-30")
        self.assertEqual([e["title"] for e in w if e["title"] == "Retreat"], ["Retreat"])
        self.assertEqual(sum(e["title"] == "Standup, daily" for e in w), 2)
        self.assertIn("BEGIN:VCALENDAR", self.call("GET", "/calendar/export.ics"))

    def test_email_sync_dedupe_and_actions(self):
        s = self.server
        self.call("POST", "/settings", {"email": {"address": "me@x.com", "password": "pw", "imap_host": "h", "username": ""}})
        st = self.call("GET", "/settings")
        self.assertNotIn("password", st["email"])
        self.assertTrue(st["email"]["has_password"])
        orig = s.mailer.fetch_new
        s.mailer.fetch_new = lambda cfg, last: ([(1, mailer.parse_message(raw_mail()))], 1)
        try:
            self.assertEqual(self.call("POST", "/email/sync", {})["new"], 1)
            self.assertEqual(self.call("POST", "/email/sync", {})["new"], 0)  # same Message-ID
        finally:
            s.mailer.fetch_new = orig
        e = self.call("GET", "/items?type=email")[0]
        self.assertEqual(e["data"]["attachments"], "plan.pdf")
        c = self.call("POST", f"/items/{e['id']}/to-contact", {})
        self.assertEqual((c["title"], c["data"]["email"]), ("Zoë", "zoe@acme.com"))
        self.assertEqual(self.call("POST", f"/items/{e['id']}/to-task", {})["type"], "task")
        self.call("POST", "/settings", {"email": {"address": "me@x.com", "password": ""}})  # blank keeps stored password
        self.assertTrue(self.call("GET", "/settings")["email"]["has_password"])

    def test_room_signaling(self):
        a = self.call("POST", "/rooms/r1/join", {"name": "A"})
        b = self.call("POST", "/rooms/r1/join", {"name": "B"})
        self.assertEqual([p["name"] for p in b["peers"]], ["A"])
        self.call("POST", "/rooms/r1/signal", {"from": b["id"], "to": a["id"], "type": "offer", "data": {"sdp": "x"}})
        got = self.call("GET", f"/rooms/r1/poll?id={a['id']}")
        self.assertEqual(got["msgs"][0]["type"], "offer")
        self.assertEqual(len(got["peers"]), 2)
        self.assertEqual(self.call("GET", f"/rooms/r1/poll?id={a['id']}")["msgs"], [])
        self.call("POST", "/rooms/r1/leave", {"id": b["id"]})
        self.assertEqual(len(self.call("GET", f"/rooms/r1/poll?id={a['id']}")["peers"]), 1)

    def test_recording_upload(self):
        it = self.call("POST", "/items", {"type": "call", "title": "Sync"})
        self.call("POST", f"/calls/{it['id']}/recording", raw=b"webmdata")
        self.assertEqual(self.call("GET", f"/items/{it['id']}")["data"]["recording"], it["id"] + ".webm")
        r = urllib.request.urlopen(self.base.replace("/api", "") + f"/recordings/{it['id']}.webm")
        self.assertEqual(r.read(), b"webmdata")


if __name__ == "__main__":
    unittest.main()

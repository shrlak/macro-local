import json, os, sys, tempfile, threading, unittest, urllib.parse, urllib.request, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MACRO_HOME", tempfile.mkdtemp())
import caldav, ics  # noqa: E402
import server  # noqa: E402

A = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:a@x\r
DTSTAMP:20260101T000000Z\r
SEQUENCE:2\r
SUMMARY:Dentist\r
DESCRIPTION:bring forms\r
DTSTART:20261112T150000Z\r
DTEND:20261112T160000Z\r
ATTENDEE;CN=Dr Who:mailto:who@x.com\r
BEGIN:VALARM\r
TRIGGER:-PT15M\r
ACTION:DISPLAY\r
DESCRIPTION:Reminder\r
END:VALARM\r
END:VEVENT\r
END:VCALENDAR\r
"""
B = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:b@x\r
SUMMARY:Standup\r
DTSTART;TZID=America/New_York:20261103T090000\r
DTEND;TZID=America/New_York:20261103T093000\r
RRULE:FREQ=WEEKLY;BYDAY=TU\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:b@x\r
RECURRENCE-ID;TZID=America/New_York:20261110T090000\r
SUMMARY:Standup (moved)\r
DTSTART;TZID=America/New_York:20261110T100000\r
DTEND;TZID=America/New_York:20261110T103000\r
END:VEVENT\r
END:VCALENDAR\r
"""
C = """BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:c@x\r
SUMMARY:Holiday\r
DTSTART;VALUE=DATE:20261120\r
DTEND;VALUE=DATE:20261122\r
END:VEVENT\r
END:VCALENDAR\r
"""
USER, PW = "me@icloud.com", "app-pw"


class Fake(BaseHTTPRequestHandler):
    store, log, n = {}, [], [0]

    def log_message(self, *a): pass

    @classmethod
    def reset(cls):
        cls.log.clear()
        cls.store.clear()
        cls.store.update({"/cals/home/a.ics": ('"1"', A), "/cals/home/b.ics": ('"1"', B), "/cals/home/c.ics": ('"1"', C)})

    def out(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def multistatus(self, responses):
        xml = ('<?xml version="1.0"?><d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">' + "".join(
            f'<d:response><d:href>{h}</d:href><d:propstat><d:prop>{p}</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response>'
            for h, p in responses) + "</d:multistatus>")
        self.out(207, xml.encode(), {"Content-Type": "application/xml"})

    def handle_any(self, method):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode() if n else ""
        Fake.log.append((method, self.path, dict(self.headers), body))
        if self.path == "/.well-known/caldav":
            return self.out(301, headers={"Location": "/"})
        if self.headers.get("Authorization") != "Basic " + base64.b64encode(f"{USER}:{PW}".encode()).decode():
            return self.out(401)
        p = self.path
        if method == "PROPFIND":
            if "current-user-principal" in body:
                return self.multistatus([(p, "<d:current-user-principal><d:href>/principal/</d:href></d:current-user-principal>")])
            if "calendar-home-set" in body:
                return self.multistatus([(p, "<c:calendar-home-set><d:href>/cals/</d:href></c:calendar-home-set>")])
            cal = lambda name, comp: f'<d:resourcetype><d:collection/><c:calendar/></d:resourcetype><d:displayname>{name}</d:displayname><c:supported-calendar-component-set><c:comp name="{comp}"/></c:supported-calendar-component-set>'
            return self.multistatus([("/cals/", "<d:resourcetype><d:collection/></d:resourcetype>"),
                                     ("/cals/home/", cal("Home", "VEVENT")), ("/cals/todo/", cal("Reminders", "VTODO"))])
        if method == "REPORT":
            return self.multistatus([(h, f"<d:getetag>{escape(e)}</d:getetag><c:calendar-data>{escape(t)}</c:calendar-data>")
                                     for h, (e, t) in Fake.store.items() if h.startswith(p)])
        if method == "PUT":
            exists = p in Fake.store
            im, inm = self.headers.get("If-Match"), self.headers.get("If-None-Match")
            if (inm == "*" and exists) or (im and (not exists or (im != "*" and im != Fake.store[p][0]))):
                return self.out(412)
            Fake.n[0] += 1
            etag = f'"v{Fake.n[0]}"'
            Fake.store[p] = (etag, body)
            return self.out(204 if exists else 201, headers={"ETag": etag})
        if method == "DELETE":
            Fake.store.pop(p, None)
            return self.out(204)
        self.out(405)

    do_PROPFIND = lambda s: s.handle_any("PROPFIND")
    do_REPORT = lambda s: s.handle_any("REPORT")
    do_PUT = lambda s: s.handle_any("PUT")
    do_DELETE = lambda s: s.handle_any("DELETE")


class PatchTests(unittest.TestCase):
    def test_patch_keeps_alarm_and_attendee(self):
        ev = {"id": "i", "title": "Dentist (moved)", "body": "new notes", "data": {"start": "2026-11-12T16:00Z", "end": "2026-11-12T17:00Z"}}
        out = ics.patch_ics(A, ev)
        self.assertEqual(out.count("BEGIN:VALARM"), 1)
        self.assertIn("DESCRIPTION:Reminder", out)            # alarm text untouched
        self.assertIn("DESCRIPTION:new notes", out)
        self.assertNotIn("bring forms", out)
        self.assertIn("ATTENDEE;CN=Dr Who:mailto:who@x.com", out)
        self.assertIn("SEQUENCE:3", out)
        self.assertIn("DTSTART:20261112T160000Z", out)
        self.assertEqual(ics.parse_ics(out)[0]["title"], "Dentist (moved)")

    def test_patch_recurring_keeps_overrides_and_wall_clock(self):
        ev = {"id": "i", "title": "Daily sync", "body": "", "data": {"start": "2026-11-03T09:00", "end": "2026-11-03T09:30", "rrule": "FREQ=WEEKLY;BYDAY=TU"}}
        out = ics.patch_ics(B, ev, tz="America/New_York")
        self.assertIn("RECURRENCE-ID;TZID=America/New_York:20261110T090000", out)
        self.assertIn("DTSTART:20261103T090000\r", out)  # floating, so it stays 9am across DST
        self.assertEqual(out.count("BEGIN:VEVENT"), 2)

    def test_single_event_written_in_utc_and_folded(self):
        out = ics.export_ics([{"id": "i", "title": "x" * 200, "data": {"start": "2026-11-05T09:00", "end": "2026-11-05T10:00", "uid": "u"}}], tz="America/New_York")
        if ics.ZoneInfo:
            self.assertIn("DTSTART:20261105T140000Z", out)
        self.assertTrue(all(len(l) <= 75 for l in out.split("\r\n")))
        self.assertEqual(ics.parse_ics(out)[0]["title"], "x" * 200)


class CalDavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.fake.server_address[1]}"
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.srv.daemon_threads = True
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.fake.shutdown(); cls.srv.shutdown()

    def call(self, method, path, body=None, ok=True):
        try:
            r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                       data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"}))
        except urllib.error.HTTPError as e:
            if ok:
                raise
            return json.loads(e.read())
        return json.loads(r.read())

    def setUp(self):
        Fake.reset()
        with server.lock:
            server.db.execute("DELETE FROM items"); server.db.execute("DELETE FROM settings"); server.db.commit()
        server.push_pending.clear()

    def connect(self):
        return self.call("POST", "/api/caldav/connect", {"url": self.url + "/.well-known/caldav", "username": USER, "password": PW, "timezone": "America/New_York"})

    def events(self):
        return {e["data"].get("uid"): e for e in self.call("GET", "/api/items?type=event")}

    def puts(self):
        return [(p, h, b) for m, p, h, b in Fake.log if m == "PUT"]

    def test_connect_errors_and_discovery(self):
        bad = self.call("POST", "/api/caldav/connect", {"url": self.url, "username": USER, "password": "wrong"}, ok=False)
        self.assertIn("Authentication failed", bad["error"])
        self.assertEqual(self.call("POST", "/api/caldav/connect", {"url": self.url, "username": "", "password": ""}, ok=False)["error"][:5], "Enter")
        r = self.connect()  # also follows the /.well-known 301
        self.assertEqual([c["name"] for c in r["calendars"]], ["Home"])  # the VTODO "Reminders" list is excluded
        st = self.call("GET", "/api/settings")
        self.assertNotIn(PW, json.dumps(st))
        self.assertEqual((st["caldav"]["connected"], st["caldav"]["username"]), (True, USER))
        self.assertTrue(st["caldav"]["default"].endswith("/cals/home/"))

    def test_sync_push_delete(self):
        self.connect()
        self.assertEqual(self.call("POST", "/api/caldav/sync", {})["events"], 3)
        ev = self.events()
        self.assertEqual(sorted(ev), ["a@x", "b@x", "c@x"])
        self.assertEqual(ev["a@x"]["data"]["start"], "2026-11-12T15:00Z")
        self.assertEqual(ev["b@x"]["data"]["start"], "2026-11-03T09:00")  # wall-clock, not UTC
        self.assertEqual((ev["c@x"]["data"]["start"], ev["c@x"]["data"]["end"]), ("2026-11-20", "2026-11-21"))
        self.call("POST", "/api/caldav/sync", {})
        self.assertEqual(len(self.events()), 3)  # idempotent

        # edit -> pushed with If-Match, alarms/attendees preserved
        Fake.log.clear()
        self.call("PUT", f"/api/items/{ev['a@x']['id']}", {"title": "Dentist!"})
        server.process_pushes()
        (path, hdr, body), = self.puts()
        self.assertEqual((path, hdr["If-Match"]), ("/cals/home/a.ics", '"1"'))
        self.assertTrue("SUMMARY:Dentist!" in body and "BEGIN:VALARM" in body and "who@x.com" in body)
        self.assertNotEqual(self.events()["a@x"]["data"]["caldav_etag"], '"1"')  # new etag stored
        # a second edit uses the new etag (no 412)
        self.call("PUT", f"/api/items/{ev['a@x']['id']}", {"title": "Dentist!!"})
        server.process_pushes()
        self.assertIn("Dentist!!", Fake.store["/cals/home/a.ics"][1])

        # brand-new local event -> created on the default calendar, in UTC
        Fake.log.clear()
        new = self.call("POST", "/api/items", {"type": "event", "title": "x", "data": {"allday": "no", "start": "2026-11-05T09:00", "end": "2026-11-05T10:00"}})
        self.call("PUT", f"/api/items/{new['id']}", {"title": "Lunch"})
        server.process_pushes()
        (path, hdr, body), = self.puts()
        self.assertTrue(path.startswith("/cals/home/") and path.endswith(".ics"))
        self.assertEqual(hdr["If-None-Match"], "*")
        if ics.ZoneInfo:
            self.assertIn("DTSTART:20261105T140000Z", body)
        got = self.call("GET", f"/api/items/{new['id']}")["data"]
        self.assertTrue(got["uid"].endswith("@macro-local") and got["caldav_href"].endswith(".ics"))

        # target "local" => nothing is pushed
        self.call("POST", "/api/caldav/target", {"target": "local"})
        Fake.log.clear()
        n2 = self.call("POST", "/api/items", {"type": "event", "title": "Private", "data": {"allday": "no", "start": "2026-11-06T09:00", "end": "2026-11-06T10:00"}})
        self.call("PUT", f"/api/items/{n2['id']}", {"title": "Private!"})
        server.process_pushes()
        self.assertEqual(self.puts(), [])
        self.call("POST", "/api/caldav/target", {"target": "auto"})

        # delete locally -> DELETE on the server
        Fake.log.clear()
        self.call("DELETE", f"/api/items/{ev['c@x']['id']}")
        server.process_pushes()
        self.assertNotIn("/cals/home/c.ics", Fake.store)

        # deleted on the server -> disappears locally; recurring event kept
        Fake.store.pop("/cals/home/a.ics")
        self.call("POST", "/api/caldav/sync", {})
        self.assertNotIn("a@x", self.events())
        self.assertIn("b@x", self.events())

    def test_conflict_is_reported_not_fatal(self):
        self.connect()
        self.call("POST", "/api/caldav/sync", {})
        ev = self.events()
        Fake.store["/cals/home/a.ics"] = ('"changed-elsewhere"', A.replace("Dentist", "Dentist (phone edit)"))
        self.call("PUT", f"/api/items/{ev['a@x']['id']}", {"title": "Mine"})
        server.process_pushes()
        err = self.call("GET", "/api/settings")["caldav"]["error"]
        self.assertIn("changed on the server", err)
        self.assertIn("Dentist (phone edit)", Fake.store["/cals/home/a.ics"][1])  # server copy untouched
        self.call("POST", "/api/caldav/sync", {})  # next sync takes the server's version and clears the error
        self.assertEqual(self.events()["a@x"]["title"], "Dentist (phone edit)")
        self.assertEqual(self.call("GET", "/api/settings")["caldav"]["error"], "")

    def test_deselect_and_disconnect(self):
        r = self.connect()
        self.call("POST", "/api/caldav/sync", {})
        self.assertEqual(len(self.events()), 3)
        self.call("POST", "/api/caldav/calendars", {"selected": [], "default": ""})
        self.assertEqual(len(self.events()), 0)
        self.call("POST", "/api/caldav/disconnect", {})
        self.assertFalse(self.call("GET", "/api/settings")["caldav"]["connected"])


if __name__ == "__main__":
    unittest.main()

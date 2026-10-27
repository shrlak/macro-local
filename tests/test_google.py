import base64, hashlib, json, os, sys, tempfile, threading, time, unittest, urllib.parse, urllib.request
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MACRO_HOME", tempfile.mkdtemp())
import google  # noqa: E402
import server  # noqa: E402


def raw_msg(mid, subject, frm, to):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = frm, to, subject, f"<{mid}@mail.gmail.com>"
    m["Date"] = "Mon, 26 Oct 2026 10:00:00 +0000"
    m.set_content(f"body of {mid}")
    return base64.urlsafe_b64encode(m.as_bytes()).decode().rstrip("=")


MSGS = {"m1": ("Old one", "ann@x.com", "me@gmail.com", ["INBOX"], "t1"),
        "m2": ("New one", "bob@x.com", "me@gmail.com", ["INBOX", "UNREAD"], "t2"),
        "s1": ("My reply", "me@gmail.com", "ann@x.com", ["SENT"], "t1")}
EVENTS = [
    {"id": "e1", "summary": "Lunch", "start": {"dateTime": "2026-11-02T12:00:00-05:00"}, "end": {"dateTime": "2026-11-02T13:00:00-05:00"}, "location": "Cafe"},
    {"id": "e2", "summary": "Offsite", "start": {"date": "2026-11-10"}, "end": {"date": "2026-11-12"}},
    {"id": "e3", "summary": "Standup", "start": {"dateTime": "2026-11-03T14:00:00Z", "timeZone": "America/New_York"},
     "end": {"dateTime": "2026-11-03T14:30:00Z"}, "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=TU"]},
    {"id": "e4", "summary": "Gone", "status": "cancelled"},
    {"id": "e3_x", "summary": "Standup (moved)", "recurringEventId": "e3", "start": {"dateTime": "2026-11-10T15:00:00Z"}, "end": {"dateTime": "2026-11-10T15:30:00Z"}},
]


class Fake(BaseHTTPRequestHandler):
    log = []
    state = {"challenge": "", "refreshes": 0, "invalid_grant": False}

    def log_message(self, *a): pass

    def reply(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def handle_any(self, method):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        Fake.log.append((method, u.path, raw))
        if u.path == "/token":
            f = dict(urllib.parse.parse_qsl(raw.decode()))
            if f.get("client_id") != "cid" or f.get("client_secret") != "csecret":
                return self.reply({"error": "invalid_client"}, 401)
            if f["grant_type"] == "authorization_code":
                ok = f["code"] == "good-code" and base64.urlsafe_b64encode(hashlib.sha256(f["code_verifier"].encode()).digest()).rstrip(b"=").decode() == Fake.state["challenge"]
                return self.reply({"access_token": "at1", "refresh_token": "rt1", "expires_in": 3600}) if ok else self.reply({"error": "invalid_grant", "error_description": "bad code"}, 400)
            if Fake.state["invalid_grant"]:
                return self.reply({"error": "invalid_grant", "error_description": "Token has been expired or revoked."}, 400)
            Fake.state["refreshes"] += 1
            return self.reply({"access_token": "at2", "expires_in": 3600})
        if u.path == "/revoke":
            return self.reply({})
        if not self.headers.get("Authorization", "").startswith("Bearer at"):
            return self.reply({"error": {"message": "unauthenticated"}}, 401)
        q = urllib.parse.parse_qs(u.query)
        p = u.path
        if p == "/gmail/v1/users/me/profile":
            return self.reply({"emailAddress": "me@gmail.com"})
        if p == "/gmail/v1/users/me/messages" and method == "GET":
            labels = set(q.get("labelIds", []))
            ids = [k for k in ("m2", "m1", "s1") if labels <= set(MSGS[k][3])]
            return self.reply({"messages": [{"id": i} for i in ids]})
        if p == "/gmail/v1/users/me/messages/send":
            return self.reply({"id": "sent9", "threadId": json.loads(raw).get("threadId", "tnew")})
        if p.endswith("/modify"):
            return self.reply({})
        if p.startswith("/gmail/v1/users/me/messages/"):
            mid = p.rsplit("/", 1)[1]
            s, f, t, labels, th = MSGS[mid]
            return self.reply({"raw": raw_msg(mid, s, f, t), "labelIds": labels, "threadId": th})
        if p == "/calendar/v3/calendars/primary/events":
            if method == "GET":
                return self.reply({"items": EVENTS})
            return self.reply({"id": "newg"})
        if p.startswith("/calendar/v3/calendars/primary/events/"):
            return self.reply({"id": p.rsplit("/", 1)[1]} if method == "PATCH" else {})
        self.reply({"error": {"message": "nope " + p}}, 404)

    do_GET = lambda s: s.handle_any("GET")
    do_POST = lambda s: s.handle_any("POST")
    do_PATCH = lambda s: s.handle_any("PATCH")
    do_DELETE = lambda s: s.handle_any("DELETE")


class GoogleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.fake.server_address[1]}"
        cls.saved = (google.AUTH_URL, google.TOKEN_URL, google.REVOKE_URL, google.API)
        google.AUTH_URL, google.TOKEN_URL, google.REVOKE_URL, google.API = base + "/auth", base + "/token", base + "/revoke", base
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.srv.daemon_threads = True
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.fake.shutdown(); cls.srv.shutdown()
        google.AUTH_URL, google.TOKEN_URL, google.REVOKE_URL, google.API = cls.saved

    def call(self, method, path, body=None):
        r = urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                   data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"}))
        t = r.read().decode()
        return json.loads(t) if r.headers["Content-Type"].startswith("application/json") else t

    def sent(self, method, suffix):
        return [json.loads(b or b"{}") for m, p, b in Fake.log if m == method and p.endswith(suffix)]

    def connect(self):
        with server.lock:
            server.db.execute("DELETE FROM items"); server.db.execute("DELETE FROM settings"); server.db.commit()
        Fake.log.clear()
        self.call("POST", "/api/google/config", {"client_id": "cid", "client_secret": "csecret", "timezone": "America/New_York"})
        url = self.call("POST", "/api/google/connect", {})["url"]
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.assertEqual(q["code_challenge_method"], "S256")
        self.assertIn("gmail.modify", q["scope"]); self.assertIn("auth/calendar", q["scope"])
        self.assertEqual(q["redirect_uri"], f"http://127.0.0.1:{self.port}/oauth/google/callback")
        Fake.state["challenge"] = q["code_challenge"]
        return q

    def finish(self, q, code="good-code"):
        page = self.call("GET", "/oauth/google/callback?" + urllib.parse.urlencode({"state": q["state"], "code": code}))
        with server.sync_guard:  # wait for the sign-in's background sync to finish
            pass
        time.sleep(0.2)
        with server.sync_guard:
            pass
        return page

    def test_flow(self):
        q = self.connect()
        self.assertIn("Connected", self.finish(q))
        st = self.call("GET", "/api/settings")["google"]
        self.assertEqual((st["connected"], st["email"], st["has_secret"]), (True, "me@gmail.com", True))
        self.assertNotIn("csecret", json.dumps(self.call("GET", "/api/settings")))
        self.assertNotIn("rt1", json.dumps(self.call("GET", "/api/settings")))
        # a replayed callback is rejected
        self.assertIn("failed", self.call("GET", "/oauth/google/callback?" + urllib.parse.urlencode({"state": q["state"], "code": "good-code"})))

        # ---- mail
        self.call("POST", "/api/google/sync", {})
        mails = {e["data"]["gmail_id"]: e for e in self.call("GET", "/api/items?type=email")}
        self.assertEqual(sorted(mails), ["m1", "m2", "s1"])
        self.assertEqual((mails["m2"]["data"]["unread"], mails["m1"]["data"]["unread"], mails["s1"]["data"]["folder"]), ("yes", "no", "sent"))
        self.assertEqual(mails["m2"]["body"], "body of m2")
        self.assertEqual(self.call("POST", "/api/email/sync", {})["new"], 0)

        # reading in Macro Local marks it read in Gmail
        self.call("PUT", f"/api/items/{mails['m2']['id']}", {"data": {"unread": "no"}})
        server.process_pushes()
        self.assertEqual(self.sent("POST", "/m2/modify"), [{"removeLabelIds": ["UNREAD"]}])

        # reply goes through the Gmail API in the same thread
        r = self.call("POST", "/api/email/send", {"to": "ann@x.com", "subject": "Re: Old one", "body": "thanks", "in_reply_to": "<m1@mail.gmail.com>"})
        self.assertEqual((r["data"]["folder"], r["data"]["thread_id"]), ("sent", "t1"))
        body = self.sent("POST", "/messages/send")[0]
        self.assertEqual(body["threadId"], "t1")
        import email
        msg = email.message_from_bytes(base64.urlsafe_b64decode(body["raw"]))
        self.assertEqual((msg["To"], msg["From"], msg["In-Reply-To"]), ("ann@x.com", "me@gmail.com", "<m1@mail.gmail.com>"))

        # ---- calendar pull
        evs = {e["data"]["gid"]: e for e in self.call("GET", "/api/items?type=event")}
        self.assertEqual(sorted(evs), ["e1", "e2", "e3"])  # cancelled + single-instance override skipped
        self.assertEqual((evs["e1"]["data"]["start"], evs["e1"]["data"]["location"]), ("2026-11-02T17:00Z", "Cafe"))
        self.assertEqual((evs["e2"]["data"]["start"], evs["e2"]["data"]["end"], evs["e2"]["data"]["allday"]), ("2026-11-10", "2026-11-11", "yes"))
        if google.ics.ZoneInfo:
            self.assertEqual(evs["e3"]["data"]["start"], "2026-11-03T09:00")  # wall-clock in the user's zone (stable across DST)
        self.assertEqual(evs["e3"]["data"]["rrule"], "FREQ=WEEKLY;BYDAY=TU")
        self.assertEqual(self.call("POST", "/api/google/sync", {})["calendar"]["events"], 3)
        self.assertEqual(len(self.call("GET", "/api/items?type=event")), 3)  # idempotent

        # ---- calendar push
        Fake.log.clear()
        self.call("PUT", f"/api/items/{evs['e1']['id']}", {"title": "Team lunch"})
        self.call("PUT", f"/api/items/{evs['e1']['id']}", {"title": "Team lunch!"})  # coalesced
        new = self.call("POST", "/api/items", {"type": "event", "title": "Local", "data": {"allday": "no", "start": "2026-11-05T09:00", "end": "2026-11-05T10:00"}})
        self.call("PUT", f"/api/items/{new['id']}", {"title": "Dentist"})
        ics_ev = self.call("POST", "/api/items", {"type": "event", "title": "Imported", "data": {"uid": "x@ics", "start": "2026-11-06", "end": "2026-11-06", "allday": "yes"}})
        self.call("PUT", f"/api/items/{ics_ev['id']}", {"title": "Imported edited"})
        server.process_pushes()
        patches = self.sent("PATCH", "/e1")
        self.assertEqual([p["summary"] for p in patches], ["Team lunch!"])
        self.assertEqual(patches[0]["start"], {"dateTime": "2026-11-02T17:00:00Z"})
        posts = self.sent("POST", "/primary/events")
        self.assertEqual(len(posts), 1)  # only "Dentist"; the .ics import is never written to Google
        self.assertEqual((posts[0]["summary"], posts[0]["start"]), ("Dentist", {"dateTime": "2026-11-05T09:00:00", "timeZone": "America/New_York"}))
        after = self.call("GET", f"/api/items/{new['id']}")["data"]
        self.assertEqual((after["gid"], after["uid"]), ("newg", "g:newg"))
        allday_body = google.event_to_google({"title": "A", "body": "", "data": {"allday": "yes", "start": "2026-11-10", "end": "2026-11-11"}}, "UTC")
        self.assertEqual((allday_body["start"], allday_body["end"]), ({"date": "2026-11-10"}, {"date": "2026-11-12"}))

        Fake.log.clear()
        self.call("DELETE", f"/api/items/{evs['e2']['id']}")
        server.process_pushes()
        self.assertTrue([1 for m, p, _ in Fake.log if m == "DELETE" and p.endswith("/e2")])

        # event deleted in Google disappears locally on the next pull
        removed = EVENTS.pop(0)
        try:
            self.call("POST", "/api/google/sync", {})
            self.assertNotIn("e1", {e["data"].get("gid") for e in self.call("GET", "/api/items?type=event")})
        finally:
            EVENTS.insert(0, removed)

        # ---- toggles + disconnect
        self.call("POST", "/api/google/config", {"calendar": False})
        n = len(Fake.log)
        self.call("PUT", f"/api/items/{evs['e3']['id']}", {"title": "Standup 2"})
        server.process_pushes()
        self.assertEqual(len(Fake.log), n)
        self.call("POST", "/api/google/disconnect", {})
        st = self.call("GET", "/api/settings")["google"]
        self.assertFalse(st["connected"])
        self.assertTrue([1 for m, p, _ in Fake.log if p == "/revoke"])

    def test_token_refresh_and_expiry(self):
        self.finish(self.connect())
        with server.lock:
            g = server.get_setting("google"); g["tokens"]["expires_at"] = 0; server.set_setting("google", g)
        Fake.state["refreshes"] = 0
        self.call("POST", "/api/google/sync", {})
        self.assertEqual(Fake.state["refreshes"], 1)
        with server.lock:
            g = server.get_setting("google"); g["tokens"]["expires_at"] = 0; server.set_setting("google", g)
        Fake.state["invalid_grant"] = True
        try:
            r = self.call("POST", "/api/google/sync", {})
            self.assertIn("Reconnect", r["error"])
        finally:
            Fake.state["invalid_grant"] = False

    def test_bad_code_and_missing_credentials(self):
        q = self.connect()
        self.assertIn("failed", self.finish(q, code="wrong"))
        self.assertFalse(self.call("GET", "/api/settings")["google"]["connected"])
        with server.lock:
            server.db.execute("DELETE FROM settings"); server.db.commit()
        with self.assertRaises(urllib.error.HTTPError) as c:
            self.call("POST", "/api/google/connect", {})
        self.assertEqual(c.exception.code, 400)


if __name__ == "__main__":
    unittest.main()

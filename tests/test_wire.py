"""Real-socket IMAP + SMTP tests: tiny fake servers speak the actual protocols to imaplib/smtplib."""
import base64, json, os, socketserver, sys, tempfile, threading, unittest, urllib.request
from email import message_from_bytes
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MACRO_HOME", tempfile.mkdtemp())
import server  # noqa: E402


def mail(n, subject):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"], m["Message-ID"] = f"Ann <ann{n}@x.com>", "me@x.com", subject, f"<w{n}@x.com>"
    m["Date"] = "Mon, 26 Oct 2026 10:0%d:00 +0000" % n
    m.set_content(f"hello {n}")
    return m.as_bytes()


MAILS = {1: mail(1, "First"), 2: mail(2, "Second"), 3: mail(3, "Third")}


class IMAP(socketserver.StreamRequestHandler):
    log = []

    def handle(self):
        self.wfile.write(b"* OK fake imap ready\r\n")
        for line in self.rfile:
            tag, _, rest = line.decode().strip().partition(" ")
            cmd = rest.upper()
            IMAP.log.append(rest)
            if cmd.startswith("CAPABILITY"):
                self.wfile.write(b"* CAPABILITY IMAP4rev1\r\n" + tag.encode() + b" OK done\r\n")
            elif cmd.startswith("LOGIN"):
                ok = [a.strip('"') for a in rest.split()[1:]] == ["me@x.com", "pw"]
                self.wfile.write(tag.encode() + (b" OK LOGIN completed\r\n" if ok else b" NO [AUTHENTICATIONFAILED] bad login\r\n"))
            elif cmd.startswith("SELECT") or cmd.startswith("EXAMINE"):
                self.wfile.write(b"* 3 EXISTS\r\n" + tag.encode() + b" OK [READ-ONLY] done\r\n")
            elif cmd.startswith("UID SEARCH"):
                lo = 1
                if "UID " in rest and ":*" in rest:
                    lo = int(rest.split("UID ")[-1].split(":")[0])
                ids = [u for u in MAILS if u >= lo] or [max(MAILS)]  # servers always return the last message for n:*
                self.wfile.write(b"* SEARCH " + " ".join(map(str, ids)).encode() + b"\r\n" + tag.encode() + b" OK done\r\n")
            elif cmd.startswith("UID FETCH"):
                u = int(rest.split()[2])
                assert "BODY.PEEK[]" in cmd, "must not mark messages read"
                raw = MAILS[u]
                self.wfile.write(b"* %d FETCH (UID %d BODY[] {%d}\r\n" % (u, u, len(raw)) + raw + b")\r\n" + tag.encode() + b" OK done\r\n")
            elif cmd.startswith("LOGOUT"):
                self.wfile.write(b"* BYE\r\n" + tag.encode() + b" OK bye\r\n")
                return
            else:
                self.wfile.write(tag.encode() + b" BAD unknown\r\n")


class SMTP(socketserver.StreamRequestHandler):
    sent = []

    def handle(self):
        w = lambda s: self.wfile.write(s.encode() + b"\r\n")
        w("220 fake smtp")
        env = {"to": []}
        while True:
            line = self.rfile.readline().decode().strip()
            u = line.upper()
            if u.startswith("EHLO") or u.startswith("HELO"):
                w("250-fake"); w("250 AUTH PLAIN")
            elif u.startswith("AUTH PLAIN"):
                ok = base64.b64decode(line.split()[2]) == b"\0me@x.com\0pw"
                w("235 ok" if ok else "535 bad credentials")
            elif u.startswith("MAIL FROM"):
                env["from"] = line; w("250 ok")
            elif u.startswith("RCPT TO"):
                env["to"].append(line.split(":", 1)[1].strip(" <>")); w("250 ok")
            elif u == "DATA":
                w("354 go"); data = []
                while True:
                    l = self.rfile.readline()
                    if l in (b".\r\n", b""):
                        break
                    data.append(l[1:] if l.startswith(b"..") else l)
                SMTP.sent.append((env["to"], b"".join(data)))
                w("250 queued")
            elif u.startswith("QUIT"):
                w("221 bye"); return
            else:
                w("250 ok")


class Quiet(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.imap, cls.smtp = Quiet(("127.0.0.1", 0), IMAP), Quiet(("127.0.0.1", 0), SMTP)
        for s in (cls.imap, cls.smtp):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        cls.srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.H)
        cls.srv.daemon_threads = True
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}/api"

    @classmethod
    def tearDownClass(cls):
        for s in (cls.imap, cls.smtp, cls.srv):
            s.shutdown()

    def call(self, method, path, body=None):
        try:
            r = urllib.request.urlopen(urllib.request.Request(self.base + path, method=method, headers={"Content-Type": "application/json"},
                                       data=json.dumps(body).encode() if body is not None else None))
        except urllib.error.HTTPError as e:
            return json.loads(e.read())
        return json.loads(r.read())

    def configure(self, password="pw"):
        self.call("POST", "/settings", {"email": {
            "address": "me@x.com", "name": "Me", "username": "me@x.com", "password": password,
            "imap_host": "127.0.0.1", "imap_port": self.imap.server_address[1], "imap_security": "none",
            "smtp_host": "127.0.0.1", "smtp_port": self.smtp.server_address[1], "smtp_security": "none"}})

    def setUp(self):
        with server.lock:
            server.db.execute("DELETE FROM items"); server.db.execute("DELETE FROM settings"); server.db.commit()
        IMAP.log.clear(); SMTP.sent.clear()

    def test_imap_sync_over_real_protocol(self):
        self.configure()
        self.assertEqual(self.call("POST", "/email/sync", {})["new"], 3)
        subjects = sorted(e["title"] for e in self.call("GET", "/items?type=email"))
        self.assertEqual(subjects, ["First", "Second", "Third"])
        e = [e for e in self.call("GET", "/items?type=email") if e["title"] == "Second"][0]
        self.assertEqual((e["body"], e["data"]["from"], e["data"]["folder"], e["data"]["unread"]), ("hello 2", "Ann <ann2@x.com>", "inbox", "yes"))
        self.assertTrue(all("STORE" not in c for c in IMAP.log))  # never modifies server flags
        # incremental: only newer UIDs, and nothing duplicated
        MAILS[4] = mail(4, "Fourth")
        try:
            self.assertEqual(self.call("POST", "/email/sync", {})["new"], 1)
            self.assertEqual(self.call("POST", "/email/sync", {})["new"], 0)
        finally:
            del MAILS[4]
        self.assertEqual(len(self.call("GET", "/items?type=email")), 4)

    def test_bad_password_reports_error(self):
        self.configure(password="nope")
        r = self.call("POST", "/email/sync", {})
        self.assertEqual(r["new"], 0)
        self.assertIn("AUTHENTICATIONFAILED", r["error"])

    def test_smtp_send_and_reply_headers(self):
        self.configure()
        it = self.call("POST", "/email/send", {"to": "Bob <bob@y.com>, c@y.com", "cc": "d@y.com", "subject": "Hi ünï", "body": "line1\n.dot line\nbye", "in_reply_to": "<w1@x.com>"})
        self.assertEqual((it["data"]["folder"], it["title"]), ("sent", "Hi ünï"))
        (rcpts, raw), = SMTP.sent
        self.assertEqual(sorted(rcpts), ["bob@y.com", "c@y.com", "d@y.com"])
        m = message_from_bytes(raw)
        self.assertEqual((m["From"], m["In-Reply-To"]), ("Me <me@x.com>", "<w1@x.com>"))
        self.assertIn(".dot line", m.get_payload(decode=True).decode())  # dot-stuffing survived
        self.assertEqual(str(__import__("email.header").header.make_header(__import__("email.header").header.decode_header(m["Subject"]))), "Hi ünï")

    def test_smtp_bad_login(self):
        self.configure(password="nope")
        r = self.call("POST", "/email/send", {"to": "a@b.com", "subject": "x", "body": "y"})
        self.assertIn("535", r["error"])
        self.assertEqual(SMTP.sent, [])


if __name__ == "__main__":
    unittest.main()

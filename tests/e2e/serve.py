"""Starts Macro Local on :8820 plus fake IMAP (8821), SMTP (8822) and iCal-feed (8823) servers for tests/e2e/full.test.js."""
import os, sys, threading, tempfile, json, time
home = tempfile.mkdtemp(); os.environ["MACRO_HOME"] = home; os.environ["MACRO_PORT"] = "8820"
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "..")); sys.path.insert(0, os.path.join(HERE, ".."))
import test_wire as W
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
imap = W.Quiet(("127.0.0.1", 8821), W.IMAP); smtp = W.Quiet(("127.0.0.1", 8822), W.SMTP)
for s in (imap, smtp): threading.Thread(target=s.serve_forever, daemon=True).start()
FEED = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:feed1@x\r\nSUMMARY:Feed Holiday\r\nDTSTART;VALUE=DATE:20261115\r\nDTEND;VALUE=DATE:20261116\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
class F(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type", "text/calendar"); self.end_headers(); self.wfile.write(FEED.encode())
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 8823), F).serve_forever, daemon=True).start()
def dump():
    while True:
        open(os.path.join(tempfile.gettempdir(), "macro-e2e-smtp.json"), "w").write(json.dumps([[t, r.decode("utf8", "replace")] for t, r in W.SMTP.sent])); time.sleep(0.3)
threading.Thread(target=dump, daemon=True).start()
print(home, flush=True)
sys.argv = ["server.py", "--no-window"]
import server; server.main()

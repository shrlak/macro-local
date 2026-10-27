import hashlib, json, os, stat, subprocess, sys, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("MACRO_HOME", tempfile.mkdtemp())
import updater  # noqa: E402
import server  # noqa: E402

DMG = b"fake-dmg-bytes-" * 5000


class GH(BaseHTTPRequestHandler):
    release = {}
    dl = DMG

    def log_message(self, *a): pass

    def do_GET(self):
        if self.path.endswith("/releases/latest"):
            if GH.release is None:
                self.send_response(500); self.end_headers(); return
            body = json.dumps(GH.release).encode()
        elif self.path.startswith("/dl/"):
            body = GH.dl
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


def release(tag, data=DMG, digest=True, prerelease=False, asset="MacroLocal.dmg"):
    base = f"http://127.0.0.1:{GH.port}"
    a = {"name": asset, "browser_download_url": f"{base}/dl/{asset}", "size": len(data)}
    if digest:
        a["digest"] = "sha256:" + hashlib.sha256(data).hexdigest()
    return {"tag_name": tag, "assets": [a], "body": "notes", "html_url": f"{base}/rel/{tag}", "prerelease": prerelease, "draft": False}


class VersionTests(unittest.TestCase):
    def test_compare(self):
        self.assertTrue(updater.is_newer("v1.0.10", "v1.0.9"))
        self.assertTrue(updater.is_newer("v1.1.0", "v1.0.99"))
        self.assertFalse(updater.is_newer("v1.0.9", "v1.0.9"))
        self.assertFalse(updater.is_newer("v1.0.8", "v1.0.9"))
        self.assertFalse(updater.is_newer("v1.0.9", "dev"))      # source/dev builds are never nagged
        self.assertFalse(updater.is_newer("nightly", "v1.0.1"))   # unparsable tags are ignored

    def test_current_version(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(updater.current_version(d), "dev")
        (d / "VERSION").write_text("v1.0.7\n")
        self.assertEqual(updater.current_version(d), "v1.0.7")
        (d / "VERSION").write_text("garbage")
        self.assertEqual(updater.current_version(d), "dev")


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gh = ThreadingHTTPServer(("127.0.0.1", 0), GH)
        GH.port = cls.gh.server_address[1]
        threading.Thread(target=cls.gh.serve_forever, daemon=True).start()
        cls.saved = updater.API
        updater.API = f"http://127.0.0.1:{GH.port}"

    @classmethod
    def tearDownClass(cls):
        cls.gh.shutdown()
        updater.API = cls.saved


class DownloadTests(Base):
    def test_latest_release_and_stage(self):
        GH.release, GH.dl = release("v1.0.5"), DMG
        info = updater.latest_release()
        self.assertEqual((info["tag"], info["size"]), ("v1.0.5", len(DMG)))
        d = Path(tempfile.mkdtemp())
        p = updater.stage(info, d)
        self.assertEqual(p.read_bytes(), DMG)
        self.assertEqual(list(d.glob("*.part")), [])
        self.assertEqual(updater.stage(info, d), p)  # already staged: no re-download
        GH.release = release("v1.0.6"); info2 = updater.latest_release()
        p2 = updater.stage(info2, d)
        self.assertEqual([x.name for x in d.glob("*.dmg")], [p2.name])  # older staged copy removed

    def test_rejects_tampered_or_truncated_downloads(self):
        d = Path(tempfile.mkdtemp())
        GH.release, GH.dl = release("v1.0.5"), b"X" * len(DMG)            # same size, wrong content
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            updater.stage(updater.latest_release(), d)
        GH.dl = DMG[:1000]                                                 # truncated
        with self.assertRaisesRegex(ValueError, "incomplete"):
            updater.stage(updater.latest_release(), d)
        self.assertEqual(list(d.iterdir()), [])                            # nothing half-written left behind

    def test_ignores_prerelease_or_missing_asset(self):
        GH.release = release("v1.0.9", prerelease=True)
        self.assertIsNone(updater.latest_release())
        GH.release = release("v1.0.9", asset="Other.zip")
        self.assertIsNone(updater.latest_release())


class ServerTests(Base):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "VERSION").write_text("v1.0.1\n")
        self.saved = (server.CODE_DIR, server.DATA_DIR, updater.can_install, updater.app_bundle, updater.apply, server.quit_app)
        server.CODE_DIR, server.DATA_DIR = self.tmp, self.tmp / "data"
        updater.can_install, updater.app_bundle = (lambda b=None: True), (lambda: self.tmp / "MacroLocal.app")
        self.applied, self.quit = [], []
        updater.apply = lambda dmg, bundle, relaunch, log, pid=None: self.applied.append((Path(dmg), Path(bundle), relaunch))
        server.quit_app = lambda: self.quit.append(1)
        with server.lock:
            server.db.execute("DELETE FROM settings"); server.db.commit()

    def tearDown(self):
        server.CODE_DIR, server.DATA_DIR, updater.can_install, updater.app_bundle, updater.apply, server.quit_app = self.saved

    def test_auto_update_stages_in_background(self):
        GH.release, GH.dl = release("v1.0.4"), DMG
        st = server.update_check()
        self.assertEqual((st["current"], st["latest"], st["available"], st["ready"], st["error"]), ("v1.0.1", "v1.0.4", True, True, ""))
        self.assertTrue(server.staged_update().is_file())

    def test_up_to_date_and_nagging(self):
        GH.release = release("v1.0.1")
        st = server.update_check()
        self.assertEqual((st["available"], st["ready"]), (False, False))

    def test_auto_off_checks_but_does_not_download_until_asked(self):
        GH.release, GH.dl = release("v1.0.4"), DMG
        with server.lock:
            server.set_setting("update", {"auto": False})
        st = server.update_check()
        self.assertEqual((st["available"], st["ready"], st["auto"]), (True, False, False))
        r = server.update_install()                      # "Restart to update" downloads first, then applies
        self.assertEqual(r, {"ok": True})
        self.assertEqual([(a[0].name, a[2]) for a in self.applied], [("MacroLocal-v1.0.4.dmg", True)])
        time.sleep(1.2); self.assertEqual(self.quit, [1])  # and then the app quits

    def test_apply_on_quit_only_when_auto_and_staged(self):
        GH.release, GH.dl = release("v1.0.4"), DMG
        server.update_check(); server.update_on_exit()
        self.assertEqual([(a[0].name, a[2]) for a in self.applied], [("MacroLocal-v1.0.4.dmg", False)])  # no relaunch on quit
        self.applied.clear()
        with server.lock:
            server.set_setting("update", {"auto": False})
        server.update_on_exit()
        self.assertEqual(self.applied, [])

    def test_cannot_self_update_from_source(self):
        updater.can_install = lambda b=None: False
        GH.release = release("v1.0.4")
        st = server.update_check()
        self.assertEqual((st["available"], st["ready"], st["page"].endswith("/rel/v1.0.4")), (True, False, True))  # shows a download link
        self.assertIn("cannot update itself", server.update_install()["error"])
        self.assertEqual(self.applied, [])

    def test_network_failure_is_reported_not_fatal(self):
        GH.release = None
        st = server.update_check()
        self.assertTrue(st["error"] and not st["available"])
        GH.release = release("v1.0.4")                   # recovers on the next check
        self.assertEqual(server.update_check()["error"], "")


FAKE_TOOLS = {
    "hdiutil": '''#!/bin/sh
case "$1" in
  attach) [ -n "$FAIL_MOUNT" ] && exit 1
    while [ $# -gt 0 ]; do [ "$1" = "-mountpoint" ] && MP="$2"; shift; done
    mkdir -p "$MP/MacroLocal.app/Contents/MacOS"; echo new > "$MP/MacroLocal.app/marker" ;;
  detach) exit 0 ;;
esac
''',
    "ditto": '#!/bin/sh\n[ -n "$FAIL_DITTO" ] && { mkdir -p "$2"; exit 1; }\ncp -R "$1" "$2"\n',
    "xattr": "#!/bin/sh\nexit 0\n",
    "open": '#!/bin/sh\necho "$@" >> "$OPEN_LOG"\n',
}


class ScriptTests(unittest.TestCase):
    """Runs the real update shell script against fake macOS tools."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        bindir = self.d / "bin"; bindir.mkdir()
        for n, body in FAKE_TOOLS.items():
            (bindir / n).write_text(body); (bindir / n).chmod(0o755)
        self.app = self.d / "Apps" / "MacroLocal.app"
        self.app.mkdir(parents=True); (self.app / "marker").write_text("old")
        self.dmg = self.d / "u.dmg"; self.dmg.write_bytes(b"dmg")
        self.script = self.d / "up.sh"; self.script.write_text(updater.SCRIPT)
        self.env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "OPEN_LOG": str(self.d / "open.log"), "TMPDIR": str(self.d)}

    def run_script(self, relaunch, **extra):
        subprocess.run(["/bin/sh", str(self.script), "999999", str(self.dmg), str(self.app), relaunch, str(self.d / "log")],
                       env={**self.env, **extra}, check=True, timeout=30)
        return (self.d / "log").read_text()

    def marker(self): return (self.app / "marker").read_text().strip()

    def test_success_replaces_app_and_relaunches(self):
        log = self.run_script("1")
        self.assertEqual(self.marker(), "new")
        self.assertIn("updated", log)
        self.assertFalse(Path(str(self.app) + ".old").exists())
        self.assertFalse(self.dmg.exists())                                  # staged download cleaned up
        self.assertEqual((self.d / "open.log").read_text().strip(), str(self.app))

    def test_quit_time_update_does_not_relaunch(self):
        self.run_script("0")
        self.assertEqual(self.marker(), "new")
        self.assertFalse((self.d / "open.log").exists())

    def test_failed_copy_rolls_back(self):
        log = self.run_script("0", FAIL_DITTO="1")
        self.assertIn("rolling back", log)
        self.assertEqual(self.marker(), "old")                               # original app restored
        self.assertFalse(Path(str(self.app) + ".old").exists())
        self.assertTrue(self.dmg.exists())

    def test_mount_failure_leaves_app_untouched(self):
        log = self.run_script("1", FAIL_MOUNT="1")
        self.assertIn("could not mount", log)
        self.assertEqual(self.marker(), "old")
        self.assertEqual((self.d / "open.log").read_text().strip(), str(self.app))  # still relaunches the existing app

    def test_waits_for_the_running_app_to_exit(self):
        pid = subprocess.run(["sh", "-c", "sleep 2 >/dev/null 2>&1 & echo $!"], capture_output=True, text=True).stdout.strip()  # orphaned, like the real app
        t0 = time.time()
        subprocess.run(["/bin/sh", str(self.script), pid, str(self.dmg), str(self.app), "0", str(self.d / "log")], env=self.env, check=True, timeout=30)
        self.assertGreaterEqual(time.time() - t0, 1.0)
        self.assertEqual(self.marker(), "new")

    def test_apply_spawns_detached_script(self):
        old = os.environ["PATH"]; os.environ["PATH"], os.environ["OPEN_LOG"], os.environ["TMPDIR"] = self.env["PATH"], self.env["OPEN_LOG"], str(self.d)
        try:
            updater.apply(self.dmg, self.app, False, self.d / "log", pid=999999)
            for _ in range(100):
                if (self.d / "log").exists() and "updated" in (self.d / "log").read_text():
                    break
                time.sleep(0.1)
        finally:
            os.environ["PATH"] = old
        self.assertEqual(self.marker(), "new")


if __name__ == "__main__":
    unittest.main()

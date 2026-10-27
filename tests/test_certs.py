"""Reproduces "CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate" (packaged macOS app) and checks the fix."""
import http.server, os, shutil, ssl, subprocess, sys, tempfile, textwrap, threading, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@unittest.skipUnless(shutil.which("openssl"), "needs the openssl CLI to mint a test certificate")
class CertTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp())
        r = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(cls.d / "k.pem"), "-out", str(cls.d / "c.pem"),
                            "-days", "2", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"], capture_output=True)
        if r.returncode:  # e.g. macOS' LibreSSL lacks -addext
            raise unittest.SkipTest("this openssl cannot mint a SAN certificate")

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                self.send_response(200); self.send_header("Content-Length", "2"); self.end_headers(); self.wfile.write(b"ok")
        cls.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cls.d / "c.pem", cls.d / "k.pem")
        cls.srv.socket = ctx.wrap_socket(cls.srv.socket, server_side=True)
        cls.url = f"https://localhost:{cls.srv.server_address[1]}/"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        # a fake macOS `security` that "exports" the certificate we trust, and logs each call
        (cls.d / "bin").mkdir()
        sec = cls.d / "bin" / "security"
        sec.write_text(f'#!/bin/sh\necho x >> "{cls.d}/security.calls"\ncat "{cls.d}/c.pem"\n')
        sec.chmod(0o755)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def run_py(self, code, **env):
        e = {k: v for k, v in os.environ.items() if k != "SSL_CERT_FILE"}
        e.update(env)
        r = subprocess.run([sys.executable, "-I", "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r})\n" + textwrap.dedent(code)],
                           env=e, capture_output=True, text=True, timeout=60)
        return r.returncode, (r.stdout + r.stderr).strip()

    FETCH = "import urllib.request; print(urllib.request.urlopen(%r, timeout=10).read().decode())"

    def test_reproduces_the_failure_without_a_trust_store(self):
        code, out = self.run_py(self.FETCH % self.url)
        self.assertNotEqual(code, 0)
        self.assertIn("CERTIFICATE_VERIFY_FAILED", out)

    def test_macos_keychain_export_fixes_it(self):
        home = self.d / "home1"; home.mkdir()
        calls = self.d / "security.calls"
        calls.unlink(missing_ok=True)
        code, out = self.run_py(f"""
            import sys, urllib.request, certs
            real = sys.platform; sys.platform = 'darwin'
            try: print('BUNDLE', certs.install({str(home)!r}, wait=True))
            finally: sys.platform = real
            {self.FETCH % self.url}
            """, PATH=f"{self.d / 'bin'}:{os.environ['PATH']}")
        self.assertEqual(code, 0, out)
        self.assertIn(str(home / "ca-bundle.pem"), out)
        self.assertTrue(out.endswith("ok"))
        self.assertIn("BEGIN CERTIFICATE", (home / "ca-bundle.pem").read_text())
        # a second launch reuses the fresh bundle instead of shelling out again
        n = len(calls.read_text().split())
        self.run_py(f"import sys, certs; sys.platform='darwin'; certs.install({str(home)!r}, wait=True)", PATH=f"{self.d / 'bin'}:{os.environ['PATH']}")
        if (home / "ca-bundle.pem").stat().st_size > 1000:
            self.assertEqual(len(calls.read_text().split()), n)

    def test_user_supplied_ca_file_wins(self):
        code, out = self.run_py(f"import certs; print(certs.install('/nonexistent'))", SSL_CERT_FILE=str(self.d / "c.pem"))
        self.assertEqual((code, out), (0, str(self.d / "c.pem")))

    def test_failed_export_does_not_crash(self):
        empty = self.d / "empty"; empty.mkdir()
        (empty / "security").write_text("#!/bin/sh\nexit 1\n"); (empty / "security").chmod(0o755)
        code, out = self.run_py(f"import sys, certs; sys.platform='darwin'; print('r', certs.install({str(self.d / 'home2')!r}, wait=True))", PATH=f"{empty}:{os.environ['PATH']}")
        self.assertEqual(code, 0, out)

    def test_first_launch_never_waits_for_a_slow_keychain(self):
        try:
            import certifi  # noqa: F401
        except ImportError:
            self.skipTest("certifi not installed")
        slow = self.d / "slowbin"; slow.mkdir(exist_ok=True)
        (slow / "security").write_text(f'#!/bin/sh\nsleep 4\ncat "{self.d}/c.pem"\n'); (slow / "security").chmod(0o755)
        home = self.d / "home3"; home.mkdir(exist_ok=True)
        code, out = self.run_py(f"""
            import sys, time, urllib.request, certs
            real = sys.platform; sys.platform = 'darwin'; sys.frozen = True
            t = time.time(); first = certs.install({str(home)!r}); took = time.time() - t
            sys.platform = real
            print('FIRST', first, 'FAST' if took < 2 else 'SLOW %.1fs' % took)
            certs._thread.join(30)
            print('LATER', __import__('os').environ['SSL_CERT_FILE'])
            {self.FETCH % self.url}
            """, PATH=f"{slow}:{os.environ['PATH']}")
        self.assertEqual(code, 0, out)
        self.assertIn("cacert.pem FAST", out)                      # started at once with the bundled certifi list
        self.assertIn(f"LATER {home / 'ca-bundle.pem'}", out)      # then switched to the keychain export
        self.assertTrue(out.endswith("ok"))                         # and the keychain bundle verifies our test server

    def test_certifi_fallback_for_frozen_builds(self):
        try:
            import certifi  # noqa: F401
        except ImportError:
            self.skipTest("certifi not installed")
        code, out = self.run_py("import sys, certs; sys.platform='linux'; sys.frozen=True; print(certs.install('/tmp'))")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.endswith("cacert.pem"))


if __name__ == "__main__":
    unittest.main()

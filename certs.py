"""Make HTTPS work in the packaged app.

A PyInstaller-bundled Python on macOS has no CA bundle (it fails with "CERTIFICATE_VERIFY_FAILED: unable to get local issuer
certificate"). We point OpenSSL at a bundle via SSL_CERT_FILE, which every stdlib client (urllib, imaplib, smtplib) honours:
  1. macOS: the roots + any extra certificates you trust, exported from the system keychains (so corporate roots work too);
  2. otherwise the bundled `certifi` file, when available;
  3. otherwise the platform default is left alone.
"""
import os
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path

KEYCHAINS = ["/System/Library/Keychains/SystemRootCertificates.plist"]  # system roots; the default search list adds login/System keychains


def _export_macos(dest):
    pems = []
    for args in (["security", "find-certificate", "-a", "-p"] + KEYCHAINS, ["security", "find-certificate", "-a", "-p"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        if "BEGIN CERTIFICATE" in out:
            pems.append(out)
    text = "\n".join(pems)
    if "BEGIN CERTIFICATE" not in text:
        return None
    tmp = dest.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(dest)
    return dest


def _default_works():
    p = ssl.get_default_verify_paths()
    return any(x and os.path.exists(x) for x in (p.cafile, p.capath, os.environ.get("SSL_CERT_FILE")))


_thread = None


def _refresh(dest):
    """Export the keychains and switch to the result. Runs in the background: the export can take a while."""
    if _export_macos(dest):
        os.environ["SSL_CERT_FILE"] = str(dest)  # every new TLS connection picks this up


def install(data_dir, wait=False):
    """Returns the CA file in use right now, or None when the platform default is fine. Never blocks on the keychain.
    Call before any HTTPS request. wait=True joins the background refresh (tests)."""
    global _thread
    if os.environ.get("SSL_CERT_FILE") and os.path.exists(os.environ["SSL_CERT_FILE"]):
        return os.environ["SSL_CERT_FILE"]  # the user chose one
    path = None
    if sys.platform == "darwin":
        dest = Path(data_dir) / "ca-bundle.pem"
        have = dest.exists() and dest.stat().st_size > 1000
        if have:
            path = dest  # use the last export immediately...
        if not (have and time.time() - dest.stat().st_mtime < 7 * 86400):
            _thread = threading.Thread(target=_refresh, args=(dest,), daemon=True)  # ...and (re)build it for next time
            _thread.start()
    if not path and (getattr(sys, "frozen", False) or not _default_works()):
        try:
            import certifi
            path = Path(certifi.where())  # immediate fallback while the keychain export runs
        except Exception:
            path = None
    if path and Path(path).exists():
        os.environ["SSL_CERT_FILE"] = str(path)
    if wait and _thread:
        _thread.join(60)
    return os.environ.get("SSL_CERT_FILE") if (path or (wait and _thread)) else None

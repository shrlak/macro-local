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
import time
from pathlib import Path

KEYCHAINS = ["/System/Library/Keychains/SystemRootCertificates.plist"]  # system roots; the default search list adds login/System keychains


def _export_macos(dest):
    pems = []
    for args in (["security", "find-certificate", "-a", "-p"] + KEYCHAINS, ["security", "find-certificate", "-a", "-p"]):
        try:
            out = subprocess.run(args, capture_output=True, text=True, timeout=30).stdout
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


def install(data_dir):
    """Returns the CA file in use, or None when the platform default is fine. Call before any HTTPS request."""
    if os.environ.get("SSL_CERT_FILE") and os.path.exists(os.environ["SSL_CERT_FILE"]):
        return os.environ["SSL_CERT_FILE"]  # the user chose one
    path = None
    if sys.platform == "darwin":
        dest = Path(data_dir) / "ca-bundle.pem"
        fresh = dest.exists() and dest.stat().st_size > 1000 and time.time() - dest.stat().st_mtime < 7 * 86400
        path = dest if fresh else _export_macos(dest)
        if not path and dest.exists():
            path = dest  # keychain export failed this time; reuse the last good one
    if not path and (getattr(sys, "frozen", False) or not _default_works()):
        try:
            import certifi
            path = Path(certifi.where())
        except Exception:
            path = None
    if path and Path(path).exists():
        os.environ["SSL_CERT_FILE"] = str(path)
        return str(path)
    return None

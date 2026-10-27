"""Self-update for the packaged macOS app, from the GitHub Releases of this repository. Standard library only.

Flow: check the latest release -> if newer, download MacroLocal.dmg in the background and verify it (size + SHA-256 when GitHub
provides it) -> apply it when the app quits (or right away on "Restart to update"): a detached shell script waits for this process
to exit, swaps the .app bundle (keeping the old one until the copy succeeds, rolling back otherwise) and optionally relaunches.
Source checkouts and apps in non-writable locations only get a "download" link.
"""
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = os.environ.get("MACRO_UPDATE_REPO", "shrlak/macro-local")
API = os.environ.get("MACRO_UPDATE_API", "https://api.github.com")
ASSET = "MacroLocal.dmg"
APP_NAME = "MacroLocal.app"


def parse_version(tag):
    """'v1.0.12' -> (1, 0, 12); anything unparsable -> ()."""
    m = re.match(r"^v?(\d+(?:\.\d+)*)$", (tag or "").strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def current_version(code_dir):
    """Version stamped into the packaged app by CI ('v1.0.N'); 'dev' when running from source."""
    try:
        v = (Path(code_dir) / "VERSION").read_text().strip()
        return v if parse_version(v) else "dev"
    except OSError:
        return "dev"


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)  # dev builds are never nagged


def _get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "MacroLocal-updater"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def latest_release():
    """-> {'tag','url','size','sha256','notes','page'} for the newest published release that has the DMG, else None."""
    rel = _get_json(f"{API}/repos/{REPO}/releases/latest")
    asset = next((a for a in rel.get("assets", []) if a.get("name") == ASSET), None)
    if not asset or rel.get("draft") or rel.get("prerelease"):
        return None
    digest = asset.get("digest") or ""
    return {"tag": rel["tag_name"], "url": asset["browser_download_url"], "size": asset.get("size", 0),
            "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else "",
            "notes": (rel.get("body") or "")[:600], "page": rel.get("html_url", "")}


def stage(info, dest_dir, progress=None):
    """Download the DMG into dest_dir and verify it. Returns the final path; raises on any mismatch."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    final = dest_dir / f"MacroLocal-{info['tag']}.dmg"
    if final.is_file() and (not info.get("size") or final.stat().st_size == info["size"]):
        return final
    part = final.with_suffix(".part")
    h, got = hashlib.sha256(), 0
    req = urllib.request.Request(info["url"], headers={"User-Agent": "MacroLocal-updater"})
    with urllib.request.urlopen(req, timeout=60) as r, open(part, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress:
                progress(got, info.get("size", 0))
    if info.get("size") and got != info["size"]:
        part.unlink(missing_ok=True)
        raise ValueError(f"Download incomplete ({got} of {info['size']} bytes)")
    if info.get("sha256") and h.hexdigest() != info["sha256"]:
        part.unlink(missing_ok=True)
        raise ValueError("Download failed its SHA-256 check")
    part.replace(final)
    for old in dest_dir.glob("MacroLocal-*.dmg"):  # keep only the newest staged download
        if old != final:
            old.unlink(missing_ok=True)
    return final


def app_bundle():
    """The running .app bundle when this is the packaged macOS app, else None."""
    if not (getattr(sys, "frozen", False) and sys.platform == "darwin"):
        return None
    for p in Path(sys.executable).resolve().parents:
        if p.suffix == ".app":
            return p
    return None


def can_install(bundle=None):
    b = bundle or app_bundle()
    return bool(b and os.access(b.parent, os.W_OK) and os.access(b, os.W_OK))


SCRIPT = r'''#!/bin/sh
# Macro Local updater. args: pid dmg app relaunch log
PID="$1"; DMG="$2"; APP="$3"; RELAUNCH="$4"; LOG="$5"
exec >>"$LOG" 2>&1
echo "== update $(date) pid=$PID dmg=$DMG app=$APP"
n=0
while kill -0 "$PID" 2>/dev/null && [ "$n" -lt 120 ]; do sleep 0.5; n=$((n+1)); done
MNT=$(mktemp -d "${TMPDIR:-/tmp}/macro-update.XXXXXX")
OK=0
if hdiutil attach "$DMG" -nobrowse -readonly -noverify -mountpoint "$MNT" -quiet; then
  NEW="$MNT/MacroLocal.app"
  if [ -d "$NEW" ]; then
    rm -rf "$APP.old"
    if mv "$APP" "$APP.old"; then
      if ditto "$NEW" "$APP"; then
        xattr -dr com.apple.quarantine "$APP" 2>/dev/null
        rm -rf "$APP.old"; OK=1; echo "updated"
      else
        echo "copy failed; rolling back"; rm -rf "$APP"; mv "$APP.old" "$APP"
      fi
    else echo "cannot move the current app aside"; fi
  else echo "no MacroLocal.app inside the dmg"; fi
  hdiutil detach "$MNT" -quiet -force
else echo "could not mount the dmg"; fi
rmdir "$MNT" 2>/dev/null
[ "$OK" = 1 ] && rm -f "$DMG"
if [ "$RELAUNCH" = 1 ]; then open "$APP"; fi
'''


def apply(dmg, bundle, relaunch, log_path, pid=None):
    """Spawn the detached updater script. The caller must exit promptly afterwards."""
    fd, path = tempfile.mkstemp(prefix="macro-updater-", suffix=".sh")
    with os.fdopen(fd, "w") as f:
        f.write(SCRIPT)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    subprocess.Popen(["/bin/sh", path, str(pid or os.getpid()), str(dmg), str(bundle), "1" if relaunch else "0", str(log_path)],
                     start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

#!/usr/bin/env python3
"""Build the macOS app bundle (dist/MacroLocal.app) with PyInstaller. Run on a Mac (CI does this; see .github/workflows).

    pip install pyinstaller && python3 build.py

PyInstaller cannot cross-compile, so the .dmg is built by GitHub Actions on a macOS runner.
"""
import subprocess, sys
from pathlib import Path

here = Path(__file__).resolve().parent
sep = ";" if sys.platform == "win32" else ":"
cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--name", "MacroLocal",
       "--osx-bundle-identifier", "com.macrolocal.app", "--add-data", f"{here / 'static'}{sep}static", str(here / "server.py")]
if (here / "VERSION").exists():  # stamped by CI; read by updater.current_version()
    cmd[-1:-1] = ["--add-data", f"{here / 'VERSION'}{sep}."]
if (here / "MacroLocal.icns").exists():
    cmd[-1:-1] = ["--icon", str(here / "MacroLocal.icns")]
sys.exit(subprocess.call(cmd, cwd=here))

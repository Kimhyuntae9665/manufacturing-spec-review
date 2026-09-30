"""Isolated actual Chrome capture for the P02 visual refit; baseline only."""
import os
import sqlite3
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import browser_check as check
from spec_review.core import Store
from spec_review.server import make_server

APP_PORT = 19102
DEBUG_PORT = 19112


def ready(url):
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1).close()
            return
        except Exception:
            time.sleep(.1)
    raise RuntimeError("local browser or app did not start")


def main():
    with tempfile.TemporaryDirectory(prefix="p02-refit-") as temp:
        database = Path(temp) / "reviews.sqlite3"
        with sqlite3.connect(f"file:{ROOT / 'data/reviews.sqlite3'}?mode=ro", uri=True) as source:
            with sqlite3.connect(database) as copy:
                source.backup(copy)
        store = Store(ROOT / "data/documents.json", database)
        server = make_server(store, APP_PORT)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        chrome = subprocess.Popen([
            "/usr/bin/google-chrome", "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-background-networking", "--remote-allow-origins=*",
            f"--remote-debugging-port={DEBUG_PORT}", f"--user-data-dir={temp}/chrome",
            "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            ready(f"http://127.0.0.1:{APP_PORT}/")
            ready(f"http://127.0.0.1:{DEBUG_PORT}/json/version")
            check.APP = f"http://127.0.0.1:{APP_PORT}"
            check.DEBUG = f"http://127.0.0.1:{DEBUG_PORT}"
            sys.argv = ["browser_check.py", "--output", "docs/demo/current"]
            check.main()
            saved = [
                ("9d70ece1ff694130bf0e09c8908e9a80", "P001", "A-reviewer", "failed", "08-real-model-failure-manual-review.png"),
                ("69943ccbf20d4727af36569711b5950b", "P001", "A-reviewer", "source_verified", "09-stored-real-model-p001.png"),
                ("00e8f204d4be46f9b2e3e4b77113d8a1", "P002", "A-reviewer", "source_verified", "10-stored-real-model-p002.png"),
                ("4fed0a2b8bad4370b33db1c0837d90fc", "P003", "B-reviewer", "source_verified", "11-stored-real-model-p003.png"),
            ]
            for identifier, part, profile, state, filename in saved:
                sys.argv = ["browser_check.py", "--output", "docs/demo/current",
                            "--stored-comparison", identifier, "--stored-part", part,
                            "--stored-profile", profile, "--expected-model-state", state,
                            "--stored-filename", filename]
                check.main()
            sys.argv = ["browser_check.py", "--output", "docs/demo/current/video", "--record-video"]
            check.main()
        finally:
            chrome.terminate()
            try:
                chrome.wait(timeout=5)
            except subprocess.TimeoutExpired:
                chrome.kill()
            server.shutdown()
            server.server_close()
            store.close()


if __name__ == "__main__":
    main()

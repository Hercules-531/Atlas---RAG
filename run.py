"""Start Atlas from VS Code with the Python Run button: open this file and run it."""

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8765"


def run_step(*args):
    print("\n> " + " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def open_when_ready():
    # The frontend build and model startup can take a while on the first run.
    for _ in range(600):
        try:
            with urllib.request.urlopen(URL + "/api/config", timeout=2) as response:
                if response.status == 200:
                    print("\nAtlas is ready at " + URL, flush=True)
                    webbrowser.open(URL)
                    return
        except (OSError, ValueError):
            time.sleep(1)
    print("\nAtlas has not responded yet. Check the terminal for errors.", flush=True)


def main():
    os.chdir(ROOT)
    uv = shutil.which("uv")
    if not uv:
        print("uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ and restart VS Code.")
        return 1
    if not (shutil.which("npm.cmd") or shutil.which("npm")):
        print("Node.js and npm are required to build the interface. Install Node.js and restart VS Code.")
        return 1
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", 8765)) == 0:
            print("Port 8765 is already in use. Stop the existing server before starting Atlas.")
            return 1

    if not (ROOT / ".env").exists():
        shutil.copyfile(ROOT / ".env.example", ROOT / ".env")
        print("Created .env from .env.example. Add PRUNE_API_KEY for Privacy mode.", flush=True)

    # Preserve the separately installed spaCy model while synchronizing dependencies.
    run_step(uv, "sync", "--python", "3.12", "--inexact")
    probe = (
        "import importlib.util; from atlas.config import DATA; "
        "ready=(DATA/'models/embeddinggemma-2-F32.gguf').is_file() or "
        "(DATA/'models/embeddinggemma-2/config.json').is_file(); "
        "raise SystemExit(0 if ready and importlib.util.find_spec('en_core_web_sm') else 1)"
    )
    if subprocess.run([uv, "run", "--no-sync", "python", "-c", probe], cwd=ROOT).returncode:
        print("\nSetting up local embedding and NER models. This may download model files.", flush=True)
        run_step(uv, "run", "--no-sync", "atlas", "setup-models")

    print("\nStarting Atlas. Keep this terminal open; press Ctrl+C to stop.", flush=True)
    threading.Thread(target=open_when_ready, daemon=True).start()
    run_step(uv, "run", "--no-sync", "atlas", "dev")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAtlas stopped.")
    except subprocess.CalledProcessError as exc:
        print(f"\nStartup failed (exit code {exc.returncode}). See the messages above.", file=sys.stderr)
        sys.exit(exc.returncode or 1)

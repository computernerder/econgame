"""Windows desktop shell with a loopback-only server and one process per save."""
from __future__ import annotations

import argparse
import os
import secrets
import socket
import threading
import time
from pathlib import Path

import uvicorn

from .application import Game
from .domain import RuleError
from .web import create_app


class SaveLock:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b")
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise RuleError("This campaign is already open. Return to its existing game window.") from exc

    def close(self):
        self.file.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Empire Manager local game")
    parser.add_argument("--browser", action="store_true", help="Serve the same interface for browser development; print its launch URL")
    parser.add_argument("--save", type=Path, default=None)
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    if args.save is None:
        save_dir=Path(__file__).resolve().parent.parent/'saves'
        pointer=save_dir/'last-campaign.txt'
        name=pointer.read_text(encoding='utf-8').strip() if pointer.exists() else 'campaign.sqlite3'
        if Path(name).name!=name or not name.endswith('.sqlite3'):name='campaign.sqlite3'
        args.save=save_dir/name
        if not args.save.exists():args.save=save_dir/'campaign.sqlite3'
    lock = SaveLock(args.save.with_suffix(".lock"))
    game = None
    server = None
    sock = socket.socket()
    try:
        game = Game(args.save, save_lock=lock)
        sock.bind(("127.0.0.1", args.port))
        host = f"127.0.0.1:{sock.getsockname()[1]}"
        token = secrets.token_urlsafe(32)
        app = create_app(game, token, host)
        config = uvicorn.Config(app, log_level="warning", access_log=False, use_colors=False)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True, name="local-web-server")
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("The local game server could not start.")
            time.sleep(0.02)
        url = f"http://{host}/?key={token}"
        if args.browser:
            print(f"Game ready: {url}", flush=True)
            print(f"Save: {args.save.resolve()}", flush=True)
            try:
                while thread.is_alive():
                    thread.join(0.5)
            except KeyboardInterrupt:
                pass
        else:
            import webview
            webview.settings["ALLOW_FILE_URLS"] = False
            webview.settings["ALLOW_DOWNLOADS"] = False
            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = False
            webview.settings["SHOW_DEFAULT_MENUS"] = False
            window = webview.create_window("Empire Manager", url, width=1440, height=960, min_size=(850, 650), background_color="#f6f5ef")
            window.events.closing += game.stop
            webview.start(gui="edgechromium" if os.name == "nt" else None, private_mode=True)
    finally:
        if game:
            game.close()
        if server:
            server.should_exit = True
            if "thread" in locals():
                thread.join(timeout=5)
        sock.close()
        lock.close()

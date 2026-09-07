"""Double-click launcher. Failures go to a visible message and a local log."""
import traceback
import sys
from pathlib import Path

if __name__ == "__main__":
    logs = Path(__file__).parent / "saves"
    logs.mkdir(exist_ok=True)
    output = (logs / "game.log").open("a", encoding="utf-8", buffering=1)
    if sys.stdout is None:
        sys.stdout = output
    if sys.stderr is None:
        sys.stderr = output
    try:
        from economic_simulation.desktop import main
        main()
    except Exception as exc:
        (logs / "startup.log").write_text(traceback.format_exc(), encoding="utf-8")
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, f"{exc}\n\nDetails: {logs / 'startup.log'}\n\nSee README.md for launch and runtime requirements.", "Empire Manager could not start", 0x10)

"""Hoops Manager — FBLA entry point."""
from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screens.manager import GameApp


def main() -> None:
    try:
        GameApp().run()
    except Exception as exc:
        report = (
            f"\n[{datetime.now().isoformat(timespec='seconds')}] "
            f"Unhandled {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
        )
        crash_log = ROOT / "crash.log"
        try:
            with crash_log.open("a", encoding="utf-8") as handle:
                handle.write(report)
        except OSError as log_error:
            print(f"Could not write {crash_log}: {log_error}", file=sys.stderr)
        print(
            f"Hoops Manager encountered an unexpected error. "
            f"Details were saved to {crash_log}.",
            file=sys.stderr,
        )
        print(report, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()

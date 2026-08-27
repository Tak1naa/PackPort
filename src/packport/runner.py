from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
from collections.abc import Callable, Sequence

from .models import CancelledError, CommandError, ProgressEvent

ProgressCallback = Callable[[ProgressEvent], None]
LogCallback = Callable[[str], None]


class CommandRunner:
    """Runs argument arrays and streams output without invoking a shell."""

    _percent = re.compile(r"(?<!\d)(100|[1-9]?\d)(?:\.\d+)?\s*%")

    def run(
        self,
        args: Sequence[str],
        *,
        stage: str,
        progress: ProgressCallback,
        log: LogCallback,
        cancel: threading.Event | None = None,
        cancelable: bool = True,
        cwd: str | os.PathLike[str] | None = None,
        timeout: float | None = None,
        env: dict[str, str] | None = None,
    ) -> str:
        if not args or any("\x00" in part for part in args):
            raise ValueError("Invalid command argument")
        progress(ProgressEvent(stage, None, stage, cancelable))
        process = subprocess.Popen(
            list(args),
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )
        output: list[str] = []
        timer: threading.Timer | None = None

        def expire() -> None:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)

        if timeout is not None:
            timer = threading.Timer(timeout, expire)
            timer.daemon = True
            timer.start()
        try:
            assert process.stdout is not None
            try:
                for raw_line in process.stdout:
                    line = raw_line.rstrip("\n")
                    output.append(line)
                    display_line = line
                    structured = None
                    if line.startswith("{"):
                        try:
                            candidate = json.loads(line)
                            if isinstance(candidate, dict) and {"stage", "message"} <= candidate.keys():
                                structured = candidate
                                display_line = str(candidate["message"])
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass
                    log(display_line)
                    if structured is not None:
                        raw_fraction = structured.get("fraction")
                        fraction = float(raw_fraction) if isinstance(raw_fraction, (int, float)) else None
                        progress(
                            ProgressEvent(
                                str(structured["stage"]),
                                fraction,
                                display_line,
                                bool(structured.get("cancelable", cancelable)) and cancelable,
                            )
                        )
                        continue
                    match = self._percent.search(line)
                    fraction = float(match.group(1)) / 100 if match else None
                    progress(ProgressEvent(stage, fraction, line or stage, cancelable))
                    if cancelable and cancel is not None and cancel.is_set() and process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                        raise CancelledError("The operation was cancelled.")
            finally:
                process.stdout.close()
            returncode = process.wait()
        finally:
            if timer is not None:
                timer.cancel()
        joined = "\n".join(output)
        if returncode != 0:
            raise CommandError(f"{stage} failed (exit status {returncode}).", returncode, joined)
        return joined


def run_capture(args: Sequence[str], timeout: float = 15) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return completed.returncode, completed.stdout.strip()

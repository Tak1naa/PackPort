from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from packport.models import ProgressEvent
from packport.runner import CommandRunner
from packport.transactions import TransactionLog


class RunnerAndLogTests(unittest.TestCase):
    def test_runner_parses_percentage_without_shell(self) -> None:
        events: list[ProgressEvent] = []
        lines: list[str] = []
        output = CommandRunner().run(
            ["/usr/bin/printf", "Downloading 42%%\\nDone\\n"],
            stage="test",
            progress=events.append,
            log=lines.append,
        )
        self.assertIn("Downloading 42%", output)
        self.assertTrue(any(event.fraction == 0.42 for event in events))

    def test_transaction_log_is_private_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = TransactionLog(Path(temporary))
            log.write("test", value="ok")
            self.assertEqual(log.path.stat().st_mode & 0o777, 0o600)
            self.assertIn('"event": "test"', log.path.read_text(encoding="utf-8"))

    def test_runner_understands_helper_json_events(self) -> None:
        events: list[ProgressEvent] = []
        lines: list[str] = []
        CommandRunner().run(
            [
                "/usr/bin/printf",
                '{"stage":"Installing","fraction":0.75,"message":"Committing","cancelable":false}\\n',
            ],
            stage="wrapper",
            progress=events.append,
            log=lines.append,
            cancelable=False,
        )
        self.assertTrue(any(event.stage == "Installing" and event.fraction == 0.75 for event in events))
        self.assertIn("Committing", lines)


if __name__ == "__main__":
    unittest.main()

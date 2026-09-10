import json
import subprocess
import sys


def test_cli_reads_stdin_and_returns_valid_json() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "phonespotter.cli"],
        input=json.dumps({"first_name": "Test", "company": "Example GmbH", "country": "DE"}),
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src:.deps", "PATH": "", "OPENROUTER_API_KEY": "dummy"},
    )
    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    assert payload["status"] in {"found", "partial", "not_found", "error"}

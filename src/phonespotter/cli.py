"""CLI entry point for PhoneSpotter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from .config import load_config
from .models import ContactInput
from .orchestrator import PhoneSpotter


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find verified B2B phone numbers.")
    parser.add_argument(
        "--config", help="Path to YAML config. Built-in defaults are used only when this option is omitted."
    )
    parser.add_argument("--input", help="Contact JSON object. If omitted, JSON is read from stdin.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        raw_input = args.input if args.input is not None else sys.stdin.read()
        if not raw_input.strip():
            raise ValueError("Provide a JSON object with --input or on stdin.")
        payload = json.loads(raw_input)
        config = load_config(Path(args.config)) if args.config else load_config()
        contact = ContactInput.model_validate(payload)
        result = PhoneSpotter(config).lookup(contact)
        print(result.model_dump_json(indent=2 if args.pretty else None))
        if result.status == "error":
            raise SystemExit(2)
    except (ValueError, json.JSONDecodeError, ValidationError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stdout)
        raise SystemExit(2)


if __name__ == "__main__":
    main()

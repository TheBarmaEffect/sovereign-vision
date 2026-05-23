"""`sovereign` command-line interface.

Subcommands:
    info        Print version and registered rules
    rules       Pretty-print the loaded rule set
    verify      Verify the audit chain of a session certificate
    demo        Launch the full dashboard demo (alias for `sovereign-vision`)
    benchmark   Run the synthetic benchmark and print FPS / latency
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sovereign import DEFAULT_RULES, __version__

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sovereign",
        description="Sovereign Vision - Constitutional Firewall for on-device CV.",
    )
    parser.add_argument("--version", action="version", version=f"sovereign {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="Print version and rule summary")
    sub.add_parser("rules", help="Pretty-print the constitutional rule set")

    verify_cmd = sub.add_parser("verify", help="Verify a session certificate's audit chain")
    verify_cmd.add_argument("path", type=Path, help="Path to a session_*.json certificate")

    demo_cmd = sub.add_parser("demo", help="Run the dashboard demo")
    demo_cmd.add_argument("--config", type=Path, default=None, help="YAML config path")
    demo_cmd.add_argument("--scenario", type=str, default="factory_floor")

    bench_cmd = sub.add_parser("benchmark", help="Run the synthetic benchmark")
    bench_cmd.add_argument("--frames", type=int, default=300)

    args = parser.parse_args(argv)

    if args.cmd == "info":
        return _cmd_info()
    if args.cmd == "rules":
        return _cmd_rules()
    if args.cmd == "verify":
        return _cmd_verify(args.path)
    if args.cmd == "demo":
        return _cmd_demo(args.config, args.scenario)
    if args.cmd == "benchmark":
        return _cmd_benchmark(args.frames)
    parser.print_help()
    return 1


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def _cmd_info() -> int:
    print(f"Sovereign Vision v{__version__}")
    print(f"Constitutional rules loaded: {len(DEFAULT_RULES)}")
    for rule in DEFAULT_RULES:
        print(f"  {rule.rule_id}  [{rule.severity.value:<8}]  {rule.name}")
    print()
    print("Research: Glass Box Framework - Northeastern University, Khoury College.")
    return 0


def _cmd_rules() -> int:
    payload = [r.to_dict() for r in DEFAULT_RULES]
    print(json.dumps(payload, indent=2))
    return 0


def _cmd_verify(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: certificate not found at {path}", file=sys.stderr)
        return 2
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        return 2

    integrity = data.pop("integrity_hash", None)
    if integrity is None:
        print("ERROR: certificate missing `integrity_hash` field", file=sys.stderr)
        return 3

    from sovereign.certificate import _integrity_hash  # type: ignore[attr-defined]

    expected = _integrity_hash(data)
    if expected != integrity:
        print("FAILED: integrity hash mismatch", file=sys.stderr)
        print(f"  expected: {expected}")
        print(f"  recorded: {integrity}")
        return 4

    print("OK: certificate integrity hash matches.")
    chain = data.get("audit_chain")
    if chain:
        print(f"     audit chain length: {chain.get('chain_length')}")
        print(f"     merkle root:        {chain.get('merkle_root')}")
    return 0


def _cmd_demo(config_path: Path | None, scenario: str) -> int:
    try:
        from demo.run_demo import main as run_demo_main
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: demo module not importable: {exc}", file=sys.stderr)
        return 5
    argv = []
    if config_path is not None:
        argv += ["--config", str(config_path)]
    argv += ["--scenario", scenario]
    return run_demo_main(argv)


def _cmd_benchmark(n_frames: int) -> int:
    from benchmarks.run_benchmark import run_benchmark

    snap = run_benchmark(n_frames=n_frames)
    print(json.dumps(snap, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

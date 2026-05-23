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

    sub.add_parser("doctor", help="Run environment diagnostics")
    sub.add_parser("init", help="Interactive setup wizard")
    sub.add_parser("packs", help="List installed rule packs")

    score_cmd = sub.add_parser(
        "score", help="Print the compliance score from a session certificate"
    )
    score_cmd.add_argument("path", type=Path)

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
    if args.cmd == "doctor":
        return _cmd_doctor()
    if args.cmd == "init":
        return _cmd_init()
    if args.cmd == "packs":
        return _cmd_packs()
    if args.cmd == "score":
        return _cmd_score(args.path)
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


def _cmd_doctor() -> int:
    """Diagnose the environment. Green/Amber/Red per check."""
    import importlib
    import platform

    from sovereign.hardware import detect

    def check(label: str, ok: bool, detail: str) -> None:
        mark = "OK   " if ok else "WARN "
        print(f"  [{mark}] {label:<32} {detail}")

    print()
    print("Sovereign Vision doctor")
    print("=======================")

    hw = detect()
    check("Apple Silicon", hw.is_apple_silicon, hw.display_chip)
    check("MLX runtime", hw.mlx_available, hw.display_mlx)
    check("Metal framework", hw.metal_available, "available" if hw.metal_available else "missing")
    check("OS", True, hw.os_version)
    check("Python version", True, platform.python_version())

    deps = [
        ("numpy", "numpy"),
        ("opencv", "cv2"),
        ("rich", "rich.console"),
        ("PIL", "PIL.Image"),
        ("yaml", "yaml"),
        ("pytest", "pytest"),
        ("hypothesis", "hypothesis"),
        ("matplotlib", "matplotlib"),
        ("fastapi", "fastapi"),
    ]
    for label, mod in deps:
        try:
            importlib.import_module(mod)
            check(f"dep: {label}", True, "ok")
        except Exception as e:
            check(f"dep: {label}", False, f"missing ({e})")

    # Constitution sanity
    try:
        from sovereign.rules import DEFAULT_RULES, validate_rule_set
        validate_rule_set(DEFAULT_RULES)
        check("constitution", True, f"{len(DEFAULT_RULES)} rules loaded")
    except Exception as e:
        check("constitution", False, str(e))

    # Run zero-PII proof
    try:
        import subprocess

        rc = subprocess.run(
            ["pytest", "tests/", "-m", "constitutional", "-q"],
            capture_output=True, text=True, timeout=30,
        )
        check("zero-PII proofs", rc.returncode == 0, "pass" if rc.returncode == 0 else "FAIL")
    except Exception as e:
        check("zero-PII proofs", False, str(e))

    print()
    return 0


def _cmd_init() -> int:
    """Interactive setup wizard."""
    print()
    print("Sovereign Vision setup wizard")
    print("=============================")
    print()
    print("This will:")
    print("  - Confirm Apple Silicon and MLX")
    print("  - List installed rule packs")
    print("  - Generate a starter config in configs/local.yaml")
    print("  - Print the next-step commands")
    print()

    from sovereign.hardware import detect
    from sovereign.packs import list_packs

    hw = detect()
    print(f"  Detected: {hw.display_chip}   {hw.display_cores}   {hw.display_memory}")
    print(f"  MLX:      {hw.display_mlx}")
    print()

    packs = list_packs()
    print(f"  Rule packs available: {', '.join(packs) if packs else '(none)'}")
    print()

    config_path = Path("configs/local.yaml")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        config_path.write_text(
            "# Sovereign Vision local config (auto-generated by `sovereign init`).\n"
            "session:\n"
            "  name: \"local-session\"\n"
            "  output_dir: \"./certificates\"\n"
            "detector:\n"
            "  model_path: \"models/yolo26m.npz\"\n"
            "  conf_threshold: 0.25\n"
        )
        print(f"  Wrote starter config to {config_path}")
    else:
        print(f"  {config_path} already exists, not overwriting")

    print()
    print("Next:")
    print("  sovereign demo                 # presenter mode")
    print("  sovereign demo --production    # production mode")
    print("  sovereign benchmark --frames 500")
    print()
    return 0


def _cmd_packs() -> int:
    from sovereign.packs import list_packs, pack_metadata

    packs = list_packs()
    if not packs:
        print("No rule packs installed.")
        return 0
    print()
    print(f"{'Pack':<14} {'Name':<36} {'Citation'}")
    print("-" * 78)
    for p in packs:
        m = pack_metadata(p)
        print(f"{p:<14} {m.get('name', '-'):<36} {m.get('citation', '-')}")
    print()
    return 0


def _cmd_score(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    score = data.get("compliance_score")
    if not score:
        print("No compliance_score field in this certificate.", file=sys.stderr)
        return 3
    print()
    print(f"Compliance score: {score['score']} / 100  (grade {score['grade']})")
    print()
    print(f"  Rule coverage:    {score['rule_coverage_score']}/30")
    print(f"  Status mix:       {score['status_mix_score']}/25")
    print(f"  Audit integrity:  {score['audit_integrity_score']}/25")
    print(f"  DP budget:        {score['dp_budget_score']}/10")
    print(f"  Redaction depth:  {score['redaction_density_score']}/10")
    print()
    print("Reasoning:")
    for k, v in (score.get("breakdown") or {}).items():
        print(f"  {k:<16} {v}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

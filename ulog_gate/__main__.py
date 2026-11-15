"""Run a local ULog check with text or JSON output."""

import argparse
import json
from pathlib import Path

from .policy import evaluate, load_policy
from .scan import ScanError, scan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="local .ulg file")
    parser.add_argument("--policy", required=True, type=Path, help="JSON evidence policy")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    args = parser.parse_args(argv)

    try:
        policy = load_policy(args.policy)
    except (OSError, ValueError, RecursionError) as exc:
        report = {
            "schema_version": 1, "status": "error",
            "findings": [{"code": "invalid_policy", "detail": str(exc)}],
        }
    else:
        try:
            with args.log.open("rb") as stream:
                evidence = scan(stream, {rule.key for rule in policy.topics})
        except (ScanError, OSError) as exc:
            if isinstance(exc, ScanError):
                status = "fail" if exc.code.startswith("truncated_frame_") else "error"
                finding = {"code": exc.code, "offset_bytes": exc.offset}
            else:
                status = "error"
                finding = {"code": "log_io_error", "detail": exc.strerror or "Cannot read log"}
            report = {"schema_version": 1, "status": status, "findings": [finding]}
        else:
            report = evaluate(policy, evidence)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"ULog evidence: {report['status'].upper()}")
        for row in report.get("topics", []):
            span = "-" if row["span_us"] is None else str(row["span_us"])
            gap = "-" if row["max_gap_us"] is None else str(row["max_gap_us"])
            print(f"  {row['topic']}[{row['instance']}]: {row['samples']} samples"
                  f", span {span} us, largest gap {gap} us")
        if "dropouts" in report:
            dropout = report["dropouts"]
            print(f"  Logger dropouts: {dropout['count']} markers, {dropout['total_ms']} ms total")
        for finding in report["findings"]:
            code = finding["code"]
            context = ", ".join(f"{key}={value}" for key, value in finding.items() if key != "code")
            print(f"  {code}" + (f": {context}" if context else ""))
    return {"pass": 0, "fail": 1, "error": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())

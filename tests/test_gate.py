import io
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from examples.generate import example_files, frame
from ulog_gate.scan import scan

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "examples" / "bench-policy.json"


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.logs = example_files()

    def run_gate(self, raw, policy=POLICY):
        path = self.path / "fixture.ulg"
        path.write_bytes(raw)
        result = subprocess.run(
            [sys.executable, "-m", "ulog_gate", str(path), "--policy", str(policy), "--json"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.stderr, "")
        self.assertEqual(path.read_bytes(), raw)
        return result.returncode, json.loads(result.stdout)

    def write_policy(self, topics, **fields):
        path = self.path / "policy.json"
        path.write_text(json.dumps({"schema_version": 1, "required_topics": topics, **fields}))
        return path

    def test_complete_recording_passes_at_exact_span_limit(self):
        exit_code, report = self.run_gate(self.logs["complete.ulg"])
        self.assertEqual((exit_code, report["status"]), (0, "pass"))
        self.assertEqual(report["topics"], [
            {"topic": "bench_sensor", "instance": 0, "samples": 51,
             "span_us": 1_000_000, "max_gap_us": 20_000},
        ])

    def test_frame_aligned_early_end_fails_evidence_without_claiming_corruption(self):
        exit_code, report = self.run_gate(self.logs["ended-early.ulg"])
        self.assertEqual((exit_code, report["status"]), (1, "fail"))
        self.assertEqual([item["code"] for item in report["findings"]],
                         ["too_few_samples", "span_below_minimum"])

    def test_reports_payload_and_header_truncation_at_the_last_frame_start(self):
        raw = self.logs["complete.ulg"]
        final_frame_offset = len(raw) - len(frame(b"D", bytes(14)))
        for count, code in [(2, "truncated_frame_header"), (6, "truncated_frame_payload")]:
            with self.subTest(code=code):
                exit_code, report = self.run_gate(raw[:final_frame_offset + count])
                self.assertEqual((exit_code, report["status"]), (1, "fail"))
                self.assertEqual(report["findings"],
                                 [{"code": code, "offset_bytes": final_frame_offset}])

    def test_instance_zero_cannot_satisfy_instance_one(self):
        policy = self.write_policy([{"name": "bench_sensor", "instance": 1}])
        exit_code, report = self.run_gate(self.logs["complete.ulg"], policy)
        self.assertEqual((exit_code, report["status"]), (1, "fail"))
        self.assertEqual(report["findings"],
                         [{"code": "missing_samples", "topic": "bench_sensor", "instance": 1}])

    def test_shadowed_or_misspelled_policy_fields_fail(self):
        policy = self.path / "bad.json"
        for content in [
            '{"schema_version":1,"schema_version":1,"required_topics":[{"name":"bench_sensor"}]}',
            '{"schema_version":1,"required_topics":[{"name":"bench_sensor","min_sample":50}]}',
            '{"schema_version":1,"required_topics":[{"name":"bench_sensor","min_samples":true}]}',
        ]:
            with self.subTest(content=content):
                policy.write_text(content)
                exit_code, report = self.run_gate(self.logs["complete.ulg"], policy)
                self.assertEqual((exit_code, report["status"]), (2, "error"))
                self.assertEqual(report["findings"][0]["code"], "invalid_policy")

    def test_one_sample_cannot_prove_gap_limit(self):
        raw = self.logs["complete.ulg"]
        policy = self.write_policy([{"name": "bench_sensor", "max_gap_ms": 25}])
        raw = raw[:-50 * len(frame(b"D", bytes(14)))]
        exit_code, report = self.run_gate(raw, policy)
        self.assertEqual((exit_code, report["status"]), (1, "fail"))
        self.assertEqual(report["findings"][0]["code"], "gap_unmeasurable")

    def test_observed_gap_and_marked_dropouts_are_independent(self):
        raw = self.logs["complete.ulg"]
        final_size = len(frame(b"D", bytes(14)))
        # Remove an interior sample. The 40 ms gap exists independently of the dropout markers.
        raw = raw[:-2 * final_size] + raw[-final_size:]
        raw += frame(b"O", struct.pack("<H", 7)) + frame(b"O", struct.pack("<H", 11))
        exit_code, report = self.run_gate(raw)
        self.assertEqual((exit_code, report["status"]), (1, "fail"))
        self.assertEqual(report["dropouts"], {"count": 2, "total_ms": 18})
        self.assertEqual([item["code"] for item in report["findings"]],
                         ["gap_above_maximum", "dropout_budget_exceeded"])
        self.assertEqual(report["findings"][0]["observed_us"], 40_000)

    def test_unsupported_feature_is_an_error_not_a_pass(self):
        raw = bytearray(self.logs["complete.ulg"])
        for flag, code in [(1, "unsupported_appended_data"), (2, "unsupported_incompatibility_flags")]:
            with self.subTest(flag=flag):
                raw[27] = flag  # Header: 16, frame header: 3, compatible bits: 8.
                exit_code, report = self.run_gate(bytes(raw))
                self.assertEqual((exit_code, report["status"]), (2, "error"))
                self.assertEqual(report["findings"], [{"code": code, "offset_bytes": 16}])

    def test_bad_required_payload_and_regressing_timestamp_cannot_pass(self):
        raw = self.logs["complete.ulg"]
        final_size = len(frame(b"D", bytes(14)))
        cases = [
            (frame(b"D", struct.pack("<HQ", 0, 2_000_000)), "invalid_required_payload_size"),
            (frame(b"D", struct.pack("<HQf", 0, 1_000_000, 1.0)), "timestamp_regression"),
        ]
        for replacement, code in cases:
            with self.subTest(code=code):
                exit_code, report = self.run_gate(raw[:-final_size] + replacement)
                self.assertEqual((exit_code, report["status"]), (2, "error"))
                self.assertEqual(report["findings"][0]["code"], code)

    def test_nested_padding_and_nonleading_timestamp(self):
        raw = self.logs["complete.ulg"][:59]  # Header and flags, no formats yet.
        raw += frame(b"F", b"sample:vector[2] axes;uint64_t timestamp;uint8_t[3] _padding0;")
        raw += frame(b"F", b"vector:int16_t value;uint8_t[2] _padding0;")
        raw += frame(b"A", struct.pack("<BH", 1, 0) + b"sample")
        for stamp in [200_000, 250_000]:
            raw += frame(b"D", struct.pack("<H8sQ", 0, bytes(8), stamp))
        report = scan(io.BytesIO(raw), {("sample", 1)})
        self.assertEqual(report.topics[("sample", 1)].max_gap_us, 50_000)

    def test_wrong_input_header_is_an_error(self):
        exit_code, report = self.run_gate(b"not a flight log" * 3)
        self.assertEqual((exit_code, report["status"]), (2, "error"))
        self.assertEqual(report["findings"], [{"code": "not_ulog", "offset_bytes": 0}])


if __name__ == "__main__":
    unittest.main()

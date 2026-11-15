# ULog Gate

A PX4 log can open normally and still end before the part of the flight you need to review. ULog Gate checks a finished recording against your test requirements while there's still time to rerun the test. See the [PX4 report on logs ending early](https://discuss.px4.io/t/ulog-files-not-recording-for-entire-flight/48878).

ULog Gate reads a local `.ulg` file and checks required uORB topic instances, sample counts, recorded spans, the largest gap between samples, and the time the logger explicitly marked as dropped. It produces a pass/fail result for a terminal or CI job. It runs on Python 3.10+ with no runtime dependencies, account, hardware, or network connection.

## Try it in a minute

Clone the repo and generate three example logs:

```sh
git clone https://github.com/prathampuglia/ulog-gate.git
cd ulog-gate
python3 examples/generate.py demo-logs
python3 -m ulog_gate demo-logs/complete.ulg --policy examples/bench-policy.json
python3 -m ulog_gate demo-logs/ended-early.ulg --policy examples/bench-policy.json
python3 -m ulog_gate demo-logs/truncated.ulg --policy examples/bench-policy.json --json
```

The three synthetic files model three different outcomes:

| Recording | Result | Why |
| --- | --- | --- |
| Complete | Pass (0) | 51 samples cover 1,000 ms, with a largest gap of 20 ms. |
| Ends on a frame boundary | Fail (1) | The file has complete frames, but only 11 samples and 200 ms of the required topic. |
| Ends inside a frame | Fail (1) | A partially written frame is reported with its zero-based byte offset. |

## Set up your own check

1. Pick the topic instances and thresholds from your test plan. Start with a short trial log to confirm naming, instance numbers, and expected cadence. Keep the policy in Git with the test.
2. Run the check after copying a **finished** log from the vehicle or simulator. Keep the output alongside the test result.
3. On failure, check whether the log was copied in full, whether the logger was configured to record the expected topic, and whether it recorded for the required duration.

```json
{
  "schema_version": 1,
  "required_topics": [
    {"name": "vehicle_attitude", "instance": 0, "min_samples": 200, "min_span_ms": 10000, "max_gap_ms": 100}
  ],
  "max_total_dropout_ms": 0
}
```

Save the example as `test-policy.json` and adjust the limits for your recording. Each topic requires at least one sample. `instance` defaults to 0 and `min_samples` to 1. Span, gap and dropout limits are optional. Write time limits in whole milliseconds. The checker compares sample times at microsecond precision. A gap limit requires at least two samples. The checker totals logger dropout markers separately from gaps between samples.

```sh
python3 -m ulog_gate flight.ulg --policy test-policy.json --json
```

Exit **0** means the log meets the policy. **1** means a policy limit was missed or a frame was truncated at the end of the file. **2** means the check could not run on the supplied inputs (for example, a bad policy, unsupported log feature, or malformed required data). JSON reports give a version, status and finding codes, plus aggregate observations when the scan completes.

## Scope and verification

A pass covers the selected topics and limits. It does not establish that the whole flight was recorded, that sensor values are accurate, or that the vehicle is safe. A log cut at a frame boundary can still pass if the retained portion meets every threshold. The scanner skips unrelated payload contents and refuses encrypted logs, appended crash data, and unknown incompatible formats. It neither uploads logs nor writes to them.

[Verification notes](docs/verification.md) show how to reproduce the checks against public PX4 logs and PyULog. If you hit a recording the checker handles incorrectly or have a real test it could support, see [Contributing](CONTRIBUTING.md).

[MIT license](LICENSE).

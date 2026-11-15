# Verification

Tested locally on macOS with Python 3.13.4. The test suite covers passing policy limits, an early end on a frame boundary, partial frame headers and payloads, missing topic instances, exact byte offsets, unmeasurable sample gaps, dropout budgets, invalid policies, unsupported features, bad sample sizes and regressing timestamps.

```sh
python3 -m unittest discover -s tests -v
```

## Cross-check with an independent parser

On both readable recordings, ULog Gate matched PyULog 1.3.0 on the sample count, first and last timestamp, and maximum gap of **every nonempty topic instance**. The logger dropout totals also matched. The two other public artifacts exercised rejection paths. This is evidence for the inputs below, rather than a compatibility claim about all PX4 releases.

| Source | Observed result |
| --- | --- |
| [PX4 PyULog legacy fixture](https://github.com/PX4/pyulog/blob/main/test/sample.ulg) | Matched 15 topic instances, 64,542 samples and four dropouts totalling 119 ms. |
| [PX4 v1.18 RC release test recording](https://github.com/PX4/flight-review-rs/issues/53) | Matched 107 topic instances, 8,355 samples and zero dropout markers. Removing the last byte of a local copy triggers `truncated_frame_payload` at byte 640860. |
| [PX4 PyULog appended data fixture](https://github.com/PX4/pyulog/blob/main/test/sample_appended.ulg) | `unsupported_appended_data` at byte 16 (exit 2). |
| [PX4 Flight Review v2 issue #24 reproduction](https://github.com/PX4/flight-review-rs/issues/24) | `invalid_data_frame` at byte 339487 (exit 2). That zero-length data frame precedes the malformed tail described in the issue; the checker reports the first error it detects. |

SHA-256 for the original artifacts, in the same order:

```text
81952e6059bc095717e7911c010e07f85749d6b04d332a5ffc51575a3fd0a558  legacy.ulg
55f016fb38864264f5066e9b886e7be0caf691921a55b738562a6ace16987db9  release-test.ulg
029136ccf20f5af2154508b1be5ce8c3abdc0706b8015791f87743e18075c3f9  appended.ulg
c0dd9b999b69711551c30f89ae1cc5053a44ba60309c2d792657a8e64d0dd592  issue-24.ulg
```

To repeat the positive comparisons from the repository root, download the public files into a temporary directory. The tool itself has no network dependency and the recordings are not bundled.

```sh
fixtures=$(mktemp -d)
curl -fsSL https://raw.githubusercontent.com/PX4/pyulog/main/test/sample.ulg -o "$fixtures/legacy.ulg"
curl -fsSL https://cdn.logs.px4.io/0dce354d-cfeb-4869-b85f-76e7c87c96c7.ulg -o "$fixtures/release-test.ulg"
shasum -a 256 "$fixtures/legacy.ulg" "$fixtures/release-test.ulg"
python3 -m venv "$fixtures/venv"
"$fixtures/venv/bin/python" -m pip install pyulog==1.3.0
"$fixtures/venv/bin/python" -m examples.compare_pyulog "$fixtures/legacy.ulg" "$fixtures/release-test.ulg"
```

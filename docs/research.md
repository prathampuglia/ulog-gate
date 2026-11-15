# Why build a PX4 flight-test evidence check?

Research snapshot: **15 November 2026**. The question was which small open-source project could solve a recurring UAV workflow problem with no aircraft, hosted service, or paid tools needed for its first release.

## What we could verify

- **A log can exist and still omit the relevant flight.** An [April 2026 PX4 operator report](https://discuss.px4.io/t/ulog-files-not-recording-for-entire-flight/48878) describes logs that do not record the whole flight. A [MAVSDK user](https://discuss.px4.io/t/using-mavsdk-python-example-script-to-download-logs/47579) reported timeouts followed by a streaming log that Flight Review flagged as corrupt.
- **Parsers and dashboards make different choices about partial logs.** [Flight Review v2 issue #24](https://github.com/PX4/flight-review-rs/issues/24) documents an actual malformed tail and a conversion failure on the reporter's branch. The older Flight Review and PyULog could read the valid prefix. The issue documents the failure mode; it does not establish how often it happens across fleets or that the current parser still fails.
- **Community interest extends beyond PX4, but is anecdotal.** A [March 2026 Reddit discussion](https://www.reddit.com/r/diydrones/comments/1rl88a2/i_need_help_with_research/) asked about unusable onboard logs in crash investigations. The reply discusses ArduPilot BIN files and corroborating them with ground logs. That supports the broader importance of evidence quality, without establishing PX4 demand or a failure rate. Public X searches did not surface a specific, verifiable first-hand report for this workflow.
- **The recorded topics depend on the test setup.** [PX4 logging documentation](https://docs.px4.io/main/en/dev_log/logging) explains logger profiles, start/stop modes, optional per-topic intervals, and the custom topic list. A valid ULog is not evidence that the logger captured a particular sensor instance for the whole measurement period.

The evidence supports a problem and an opportunity for a small tool. It does not yet establish adoption, willingness to switch tools, or how often users would rerun a test because of the result.

## Closest alternatives

| Tool | Where it overlaps | The narrower job ULog Gate does |
| --- | --- | --- |
| [PyULog `ulog_info`](https://github.com/PX4/pyulog/blob/main/pyulog/info.py) | Shows a file's duration, topic sample counts, corruption indication and dropout summaries. A short custom script around PyULog can reproduce these checks. | A ready-to-run JSON policy for per-instance presence, minimum span and maximum gaps; CI exit codes; no NumPy or installation needed on the test machine. |
| [PX4 Flight Review](https://docs.px4.io/main/en/log/flight_review) and [Flight Review v2](https://github.com/PX4/flight-review-rs) | Inspect sampling regularity and dropouts; the newer tool converts logs and runs diagnostics, with CI support for its analyzers. | Answer an acceptance question before conversion or diagnosis, including on a file that still parses but ends too early for the test plan. |
| [PX4 Dataset Builder](https://github.com/LodeStonedrones/px4-dataset-builder) | Closest open-source overlap: missing-data findings, gap-aware synchronization, data quality reports and dataset validation. | Check declared raw topic instances before building any dataset; produce a single verdict without resampling or creating derived flight data. |
| [Foxborne](https://docs.foxborne.com/collect/formats/px4-ulog) and [Bellerophon](https://www.lnbfederal.com/bellerophon/docs/) | Document truncated-log quarantine and broader recording-quality workflows, respectively. | A portable, standalone open-source command for specifically checking a versioned PX4 test policy. |
| [ulog_repair](https://github.com/bakiemrebulut/ulog_repair) | Attempts to write a repaired copy of a broken recording. | Retain the original and reject insufficient evidence even when parts remain readable. |

Searches covered GitHub repository names/descriptions, PyPI-indexed tools, PX4 upstream docs and issues, Reddit, and public X indexing. Terms included `ulog logging coverage`, `ulog integrity`, `ulog repair`, `px4 log validation` and PX4-specific queries for required topics and sample gaps. No exact public match surfaced for the standalone workflow above. That is a bounded search result, not proof that no private script or overlooked tool does it. The verifiable difference is the workflow and scope, not a novel parsing algorithm.

## What did not make the cut

| Direction | Useful signal | Decision |
| --- | --- | --- |
| Flight-log anonymization | [Reddit discussion about keeping logs private](https://www.reddit.com/r/drones/comments/1rmttol/major_updates_for_opendronelog_free_opensource/) and [PX4's log sharing instructions](https://docs.px4.io/main/en/getting_started/flight_reporting). | Defer. [PX4 Dataset Builder](https://github.com/LodeStonedrones/px4-dataset-builder) already offers PX4 anonymization, and [TrashBin](https://github.com/mishaturnbull/TrashBin) handles selective ArduPilot packet removal. Proving that output doesn't leak sensitive data is a larger job. |
| Firmware parameter migration | [ArduPilot users reported write failures after firmware updates](https://discuss.ardupilot.org/t/new-4-7-2-and-write-parameters-fail-always/145971). | Defer. [Methodic Configurator](https://ardupilot.github.io/MethodicConfigurator/ARCHITECTURE_parameter_upload.html) already handles comparison and upload. Legacy migration rules are version-dependent, and incorrect advice is costly. |
| Another flight simulator or crash dashboard | [Recent simulator community launch](https://www.reddit.com/r/ardupilot/comments/1x1b5fx/i_built_a_drone_flight_simulator_that_runs_in_a/) and [ulog-why](https://github.com/reacherwu/ulog-why) show active development. | Defer. Simulation fidelity and root cause attribution need wider validation. A test evidence check is cheaper to verify and can sit beside those tools. |

The flight-test lens favored checking evidence before teardown. The maintainer lens found strong overlap with tools that already display these metrics. The implementation lens favored one input format, a few measurable limits and an independent parser comparison. Together that supports a small release and a user trial, rather than a new dashboard. Confidence: high that the recording failure modes occur; moderate that this particular workflow is distinct in public tooling; early evidence only for demand.

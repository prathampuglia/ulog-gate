# Contribution plan

Build a public record of test engineering through small changes with visible results. Each change should have a concrete case, a reproduction, and a check someone else can run.

| Week | Small deliverable | Definition of done |
| --- | --- | --- |
| 1 | Publish the PX4 evidence checker and its demo. | Three sample outcomes are reproducible without hardware. Verification against an independent parser is documented. |
| 2 | Try one end-to-end PX4 SITL bench run. | Publish the simulator/version, test procedure, policy and outcome. Change one logger setting and reproduce a failed evidence check. Avoid uploading unrelated or unauthorized recordings. |
| 3 | Prepare one upstream contribution. | Check for a current reproducer or an open docs issue in PyULog or PX4's logging guide. Offer a small fixture, documentation correction, or reproducible report that the maintainer can use. |
| 4 | Fix one limitation that surfaced in use. | Prefer the smallest change that helps a real workflow. Candidates: add report hashes to tie a result to its exact log and policy, or compare topic coverage between recordings. Add ArduPilot support only if a real user needs it and a separate BIN fixture verifies it. |

For a feature request, describe the test, the evidence you expected and the result the tool gave. For a bug, include the CLI version or commit, the policy, the output and a small synthetic example if possible. Run the test suite before submitting a change. A useful issue, fixture, or upstream patch is a better portfolio entry than many commits that make no observable change.

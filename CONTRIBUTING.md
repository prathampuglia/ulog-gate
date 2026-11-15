# Contributing to ULog Gate

If the checker gives an unexpected result, open an issue with the commit or release version, your JSON policy, and the checker output. Include a small synthetic example if you can reproduce the behavior with one. Review any recording before sharing it publicly because ULogs can contain locations and other sensitive details.

If you'd like support for a different check, describe the test you're running and what evidence you need the recording to contain.

Before submitting a code change, run the test suite from the repository root.

```sh
python3 -m unittest discover -s tests -v
```

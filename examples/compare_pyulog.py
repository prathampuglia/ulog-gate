"""Optional independent timing cross-check. Requires PyULog in the test environment."""

import argparse
from pathlib import Path

from pyulog import ULog

from ulog_gate.scan import scan


def compare(path: Path) -> None:
    log = ULog(str(path))
    expected = {
        (item.name, item.multi_id): item.data["timestamp"]
        for item in log.data_list if len(item.data["timestamp"])
    }
    if not expected or log.file_corruption:
        raise SystemExit(f"{path.name}: comparison requires a readable, nonempty source log")
    with path.open("rb") as stream:
        result = scan(stream, set(expected))

    for topic, values in expected.items():
        times = [int(value) for value in values]
        want = (len(times), times[0], times[-1],
                max((b - a for a, b in zip(times, times[1:])), default=None))
        actual = result.topics[topic]
        got = (actual.samples, actual.first_us, actual.last_us, actual.max_gap_us)
        if got != want:
            raise SystemExit(f"{path.name}: {topic} expected {want}, got {got}")
    dropout_count = len(log.dropouts)
    dropout_ms = sum(item.duration for item in log.dropouts)
    if (result.dropout_count, result.total_dropout_ms) != (dropout_count, dropout_ms):
        raise SystemExit(f"{path.name}: dropout summaries differ")
    samples = sum(item.samples for item in result.topics.values())
    print(f"{path.name}: matched {len(expected)} instances, {samples} samples, "
          f"{dropout_count} dropouts ({dropout_ms} ms)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, nargs="+")
    for path in parser.parse_args().log:
        compare(path)


if __name__ == "__main__":
    main()

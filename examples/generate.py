"""Generate small synthetic logs; these contain no flight or location data."""

import argparse
import struct
from pathlib import Path


def frame(tag: bytes, body: bytes) -> bytes:
    return struct.pack("<Hc", len(body), tag) + body


def example_files() -> dict[str, bytes]:
    # ULog header, flags and a synthetic sensor topic.
    prefix = b"\x55\x4c\x6f\x67\x01\x12\x35\x01" + struct.pack("<Q", 1_000_000)
    prefix += frame(b"B", bytes(40))
    prefix += frame(b"F", b"bench_sensor:uint64_t timestamp;float value;")
    prefix += frame(b"A", struct.pack("<BH", 0, 0) + b"bench_sensor")
    samples = [
        frame(b"D", struct.pack("<HQf", 0, 1_000_000 + index * 20_000, 1.0))
        for index in range(51)
    ]
    good = prefix + b"".join(samples)
    return {
        "complete.ulg": good,
        "ended-early.ulg": prefix + b"".join(samples[:11]),
        "truncated.ulg": good[:-2],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for name, content in example_files().items():
        path = args.directory / name
        with path.open("xb") as stream:
            stream.write(content)
        print(path)


if __name__ == "__main__":
    main()

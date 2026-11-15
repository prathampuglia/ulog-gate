"""Streaming ULog framing and timing checks for selected uORB instances."""

import re
import struct
from dataclasses import dataclass
from typing import BinaryIO

MAGIC = b"\x55\x4c\x6f\x67\x01\x12\x35"
TOPIC = re.compile(r"[a-zA-Z0-9_/-]+")
FIELD = re.compile(r"([a-zA-Z0-9_/-]+)(?:\[([0-9]{1,5})\])? ([a-zA-Z0-9_]+)")
BASIC = {
    "char": 1, "bool": 1, "int8_t": 1, "uint8_t": 1,
    "int16_t": 2, "uint16_t": 2,
    "int32_t": 4, "uint32_t": 4, "float": 4,
    "int64_t": 8, "uint64_t": 8, "double": 8,
}
TopicKey = tuple[str, int]


class ScanError(ValueError):
    def __init__(self, code: str, offset: int):
        self.code = code
        self.offset = offset
        super().__init__(f"{code} at byte {offset}")


@dataclass(frozen=True)
class Layout:
    full_size: int
    unpadded_size: int
    timestamp: int | None


@dataclass
class Timing:
    samples: int = 0
    first_us: int | None = None
    last_us: int | None = None
    max_gap_us: int | None = None

    def add(self, timestamp: int, offset: int) -> None:
        if self.last_us is None:
            self.first_us = timestamp
        elif timestamp < self.last_us:
            raise ScanError("timestamp_regression", offset)
        else:
            self.max_gap_us = max(self.max_gap_us or 0, timestamp - self.last_us)
        self.last_us = timestamp
        self.samples += 1


@dataclass
class Evidence:
    topics: dict[TopicKey, Timing]
    dropout_count: int = 0
    total_dropout_ms: int = 0


class Formats:
    def __init__(self) -> None:
        self.raw: dict[str, str] = {}
        self.layouts: dict[str, Layout] = {}

    def add(self, text: str, offset: int) -> None:
        name, sep, fields = text.partition(":")
        if not sep or not TOPIC.fullmatch(name) or name in self.raw or name in BASIC:
            raise ScanError("invalid_format_definition", offset)
        self.raw[name] = fields

    def layout(self, name: str, offset: int, stack: tuple[str, ...] = ()) -> Layout:
        if name in self.layouts:
            return self.layouts[name]
        if name in stack or len(stack) >= 64:
            raise ScanError("invalid_format_nesting", offset)
        if name not in self.raw:
            raise ScanError("missing_format_definition", offset)
        size = unpadded = 0
        timestamp = None
        names: set[str] = set()
        for raw in self.raw[name].removesuffix(";").split(";"):
            field = FIELD.fullmatch(raw)
            if field is None:
                raise ScanError("invalid_format_field", offset)
            kind, length, field_name = field.groups()
            count = int(length) if length else 1
            if not count or field_name in names:
                raise ScanError("invalid_format_field", offset)
            names.add(field_name)
            if field_name == "timestamp":
                if kind != "uint64_t" or length is not None:
                    raise ScanError("invalid_timestamp_field", offset)
                timestamp = size
            width = BASIC.get(kind)
            if width is None:
                width = self.layout(kind, offset, (*stack, name)).full_size
            size += width * count
            if size > 65533:  # The frame payload also includes a 2-byte message ID.
                raise ScanError("invalid_format_size", offset)
            if not field_name.startswith("_padding"):
                unpadded = size
        result = Layout(size, unpadded, timestamp)
        self.layouts[name] = result
        return result


def scan(stream: BinaryIO, required: set[TopicKey]) -> Evidence:
    """Read a regular ULog once and aggregate only the requested instances."""
    def ascii_text(data: bytes, offset: int) -> str:
        try:
            return data.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ScanError("invalid_frame_text", offset) from exc

    evidence = Evidence({key: Timing() for key in required})
    header = stream.read(16)
    if len(header) != 16:
        raise ScanError("invalid_header", 0)
    if not header.startswith(MAGIC):
        raise ScanError("not_ulog", 0)
    version = header[7]
    if version not in (0, 1):
        raise ScanError("unsupported_version", 7)

    formats = Formats()
    subscriptions: dict[int, TopicKey] = {}
    used_ids: set[int] = set()
    active_required: set[TopicKey] = set()
    data_seen = flags_seen = False
    offset = 16
    while True:
        frame = stream.read(3)
        if not frame:
            break
        if len(frame) != 3:
            raise ScanError("truncated_frame_header", offset)
        size, tag = struct.unpack("<Hc", frame)
        body = stream.read(size)
        if len(body) != size:
            raise ScanError("truncated_frame_payload", offset)

        if tag == b"B":
            if offset != 16 or size < 40:
                raise ScanError("invalid_flags_frame", offset)
            flags_seen = True
            incompatible = body[8:16]
            if incompatible[0] & 0xFE or any(incompatible[1:]):
                raise ScanError("unsupported_incompatibility_flags", offset)
            if incompatible[0] & 1:
                raise ScanError("unsupported_appended_data", offset)
            if any(body[16:40]):
                raise ScanError("invalid_appended_offsets", offset)
        elif tag == b"F":
            formats.add(ascii_text(body, offset), offset)
        elif tag == b"A":
            if size < 4:
                raise ScanError("invalid_subscription", offset)
            instance, msg_id = struct.unpack_from("<BH", body)
            name = ascii_text(body[3:], offset)
            if not TOPIC.fullmatch(name) or name not in formats.raw or msg_id in used_ids:
                raise ScanError("invalid_subscription", offset)
            key = (name, instance)
            if key in required:
                if key in active_required:
                    raise ScanError("overlapping_required_subscription", offset)
                active_required.add(key)
            subscriptions[msg_id] = key
            used_ids.add(msg_id)
        elif tag == b"R":
            if size != 2:
                raise ScanError("invalid_remove_subscription", offset)
            msg_id, = struct.unpack("<H", body)
            removed = subscriptions.pop(msg_id, None)
            if removed is None:
                raise ScanError("unknown_subscription", offset)
            active_required.discard(removed)
        elif tag == b"D":
            if size < 2:
                raise ScanError("invalid_data_frame", offset)
            msg_id, = struct.unpack_from("<H", body)
            if msg_id not in subscriptions:
                raise ScanError("unknown_subscription", offset)
            data_seen = True
            key = subscriptions[msg_id]
            if key in required:
                timing = evidence.topics[key]
                layout = formats.layout(key[0], offset)
                if layout.timestamp is None:
                    raise ScanError("missing_timestamp_field", offset)
                if size - 2 not in (layout.full_size, layout.unpadded_size):
                    raise ScanError("invalid_required_payload_size", offset)
                timestamp, = struct.unpack_from("<Q", body, 2 + layout.timestamp)
                timing.add(timestamp, offset)
        elif tag == b"O":
            if size != 2:
                raise ScanError("invalid_dropout_frame", offset)
            evidence.dropout_count += 1
            evidence.total_dropout_ms += struct.unpack("<H", body)[0]

        offset += 3 + size
    if version == 1 and not flags_seen:
        raise ScanError("missing_flags_frame", 16)
    if not data_seen:
        raise ScanError("no_logged_data", offset)
    return evidence

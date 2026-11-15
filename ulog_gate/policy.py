"""Parse an explicit test policy and evaluate exact microsecond metrics."""

import json
from dataclasses import dataclass
from pathlib import Path

from .scan import TOPIC, Evidence, TopicKey


@dataclass(frozen=True)
class Requirement:
    name: str
    instance: int
    min_samples: int
    min_span_ms: int | None
    max_gap_ms: int | None

    @property
    def key(self) -> TopicKey:
        return self.name, self.instance


@dataclass(frozen=True)
class Policy:
    topics: tuple[Requirement, ...]
    max_total_dropout_ms: int | None


def _keys(value: object, allowed: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    extra = sorted(value.keys() - allowed)
    if extra:
        raise ValueError(f"{label} contains unknown field: {extra[0]!r}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate policy key: {key!r}")
        obj[key] = value
    return obj


def _integer(obj: dict, key: str, minimum: int, default: int | None = None) -> int | None:
    if key not in obj:
        return default
    value = obj[key]
    if type(value) is not int or value < minimum:
        raise ValueError(f"{key} must be an integer >= {minimum}")
    return value


def load_policy(path: Path) -> Policy:
    policy = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    _keys(policy, {"schema_version", "required_topics", "max_total_dropout_ms"}, "policy")
    if type(policy.get("schema_version")) is not int or policy["schema_version"] != 1:
        raise ValueError("schema_version must be 1")
    topics = policy.get("required_topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError("required_topics must be a nonempty array")
    rules: dict[TopicKey, Requirement] = {}
    for item in topics:
        _keys(item, {"name", "instance", "min_samples", "min_span_ms", "max_gap_ms"},
              "topic requirement")
        name = item.get("name")
        if not isinstance(name, str) or not TOPIC.fullmatch(name):
            raise ValueError("name must be a ULog topic name")
        instance = _integer(item, "instance", 0, 0)
        if instance > 255:
            raise ValueError("instance must be <= 255")
        rule = Requirement(name, instance, _integer(item, "min_samples", 1, 1),
                           _integer(item, "min_span_ms", 1),
                           _integer(item, "max_gap_ms", 1))
        if rule.key in rules:
            raise ValueError(f"duplicate topic requirement: {name}[{instance}]")
        rules[rule.key] = rule
    return Policy(tuple(rules[key] for key in sorted(rules)),
                  _integer(policy, "max_total_dropout_ms", 0))


def evaluate(policy: Policy, evidence: Evidence) -> dict:
    findings = []
    observations = []
    for rule in policy.topics:
        timing = evidence.topics[rule.key]
        span = timing.last_us - timing.first_us if timing.samples else None
        label = {"topic": rule.name, "instance": rule.instance}
        observations.append({
            **label, "samples": timing.samples, "span_us": span, "max_gap_us": timing.max_gap_us,
        })
        if not timing.samples:
            findings.append({"code": "missing_samples", **label})
            continue
        if timing.samples < rule.min_samples:
            findings.append({"code": "too_few_samples", **label,
                             "observed": timing.samples, "limit": rule.min_samples})
        if rule.min_span_ms is not None and span < rule.min_span_ms * 1000:
            findings.append({"code": "span_below_minimum", **label,
                             "observed_us": span, "limit_us": rule.min_span_ms * 1000})
        if rule.max_gap_ms is not None:
            limit = rule.max_gap_ms * 1000
            if timing.max_gap_us is None:
                findings.append({"code": "gap_unmeasurable", **label, "limit_us": limit})
            elif timing.max_gap_us > limit:
                findings.append({"code": "gap_above_maximum", **label,
                                 "observed_us": timing.max_gap_us, "limit_us": limit})
    limit = policy.max_total_dropout_ms
    if limit is not None and evidence.total_dropout_ms > limit:
        findings.append({"code": "dropout_budget_exceeded",
                         "observed_ms": evidence.total_dropout_ms, "limit_ms": limit})

    return {
        "schema_version": 1,
        "status": "fail" if findings else "pass",
        "topics": observations,
        "dropouts": {"count": evidence.dropout_count, "total_ms": evidence.total_dropout_ms},
        "findings": findings,
    }

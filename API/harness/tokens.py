from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


def _log(msg: str) -> None:
    print(f"[API/harness/tokens.py] {msg}")


@dataclass
class UsageRecord:
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    model_calls: int = 0
    total_cost_usd: float = 0.0


PRICES_PER_1K = {
    "input": 0.015,
    "output": 0.075,
    "cache_read": 0.003,
    "cache_write": 0.018,
}


def estimate_cost(usage: UsageRecord) -> float:
    return (
        usage.input_tokens / 1000 * PRICES_PER_1K["input"]
        + usage.output_tokens / 1000 * PRICES_PER_1K["output"]
        + usage.cache_read_tokens / 1000 * PRICES_PER_1K["cache_read"]
        + usage.cache_write_tokens / 1000 * PRICES_PER_1K["cache_write"]
    )


def parse_usage(payload: Dict[str, Any]) -> UsageRecord:
    usage = payload.get("usage", {})
    record = UsageRecord(
        input_tokens=int(usage.get("input_tokens", 0)),
        cache_read_tokens=int(usage.get("cache_read_input_tokens", 0)),
        cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0)),
        output_tokens=int(usage.get("output_tokens", 0)),
        model_calls=1,
    )
    record.total_cost_usd = round(estimate_cost(record), 6)
    _log(
        f"usage in={record.input_tokens}, cache_r={record.cache_read_tokens}, "
        f"cache_w={record.cache_write_tokens}, out={record.output_tokens}, cost={record.total_cost_usd}"
    )
    return record


def add_usage(total: UsageRecord, inc: UsageRecord) -> UsageRecord:
    merged = UsageRecord(
        input_tokens=total.input_tokens + inc.input_tokens,
        cache_read_tokens=total.cache_read_tokens + inc.cache_read_tokens,
        cache_write_tokens=total.cache_write_tokens + inc.cache_write_tokens,
        output_tokens=total.output_tokens + inc.output_tokens,
        model_calls=total.model_calls + inc.model_calls,
    )
    merged.total_cost_usd = round(total.total_cost_usd + inc.total_cost_usd, 6)
    return merged

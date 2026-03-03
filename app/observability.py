from __future__ import annotations

from observability.trace import TraceConfig, Tracer

TRACER = Tracer(
    TraceConfig(
        log_path="traces/agent_trace.jsonl",
        redact_keys={"authorization", "api_key", "openai_api_key"},
    )
)

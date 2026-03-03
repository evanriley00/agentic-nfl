from __future__ import annotations

import json
import os
import socket
import threading
import time
import traceback
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ms_since(start_perf: float) -> int:
    return int(round((time.perf_counter() - start_perf) * 1000))


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex}"


def _safe_json(obj: Any) -> Any:
    try:
        json.dumps(obj)
        return obj
    except TypeError:
        return str(obj)


def _redact(obj: Any, redact_keys: Optional[set[str]] = None) -> Any:
    if redact_keys is None or not redact_keys:
        return obj

    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in redact_keys:
                out[k] = "***REDACTED***"
            else:
                out[k] = _redact(v, redact_keys)
        return out

    if isinstance(obj, (list, tuple)):
        return [_redact(x, redact_keys) for x in obj]

    return obj


@dataclass(frozen=True)
class TraceConfig:
    log_path: str = "traces/agent_trace.jsonl"
    service_name: str = "agentic-nfl"
    env: str = os.getenv("ENV", "local")
    host: str = socket.gethostname()
    redact_keys: Optional[set[str]] = None


class JsonlWriter:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def write(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")


class Tracer:
    def __init__(self, config: TraceConfig):
        self.config = config
        self.writer = JsonlWriter(config.log_path)

    def start_trace(
        self,
        *,
        run_name: str,
        input_summary: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Trace":
        trace_id = _new_id("tr_")
        return Trace(
            tracer=self,
            trace_id=trace_id,
            run_name=run_name,
            input_summary=input_summary,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )

    def emit(self, event: Dict[str, Any]) -> None:
        payload = _redact(event, self.config.redact_keys)
        payload = _safe_json(payload)
        self.writer.write(payload)


class Trace:
    def __init__(
        self,
        *,
        tracer: Tracer,
        trace_id: str,
        run_name: str,
        input_summary: Optional[str],
        user_id: Optional[str],
        session_id: Optional[str],
        metadata: Dict[str, Any],
    ):
        self.tracer = tracer
        self.trace_id = trace_id
        self.run_name = run_name
        self.input_summary = input_summary
        self.user_id = user_id
        self.session_id = session_id
        self.metadata = metadata

        self._start_perf = time.perf_counter()
        self._root_span_id = _new_id("sp_")

    def run_start(self) -> None:
        self.tracer.emit({
            "ts": _utc_iso(),
            "event": "run_start",
            "trace_id": self.trace_id,
            "span_id": self._root_span_id,
            "parent_span_id": None,
            "service": self.tracer.config.service_name,
            "env": self.tracer.config.env,
            "host": self.tracer.config.host,
            "run_name": self.run_name,
            "input_summary": self.input_summary,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
        })

    def run_end(self, *, status: str, output_summary: Optional[str] = None) -> None:
        self.tracer.emit({
            "ts": _utc_iso(),
            "event": "run_end",
            "trace_id": self.trace_id,
            "span_id": self._root_span_id,
            "parent_span_id": None,
            "service": self.tracer.config.service_name,
            "env": self.tracer.config.env,
            "host": self.tracer.config.host,
            "run_name": self.run_name,
            "status": status,
            "duration_ms": _ms_since(self._start_perf),
            "output_summary": output_summary,
        })

    def log_decision(
        self,
        *,
        step: str,
        decision: str,
        rationale: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
    ) -> None:
        self.tracer.emit({
            "ts": _utc_iso(),
            "event": "decision",
            "trace_id": self.trace_id,
            "span_id": _new_id("ev_"),
            "parent_span_id": parent_span_id or self._root_span_id,
            "step": step,
            "decision": decision,
            "rationale": rationale,
            "data": data or {},
        })

    def log_event(
        self,
        *,
        event: str,
        data: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
    ) -> None:
        self.tracer.emit({
            "ts": _utc_iso(),
            "event": event,
            "trace_id": self.trace_id,
            "span_id": _new_id("ev_"),
            "parent_span_id": parent_span_id or self._root_span_id,
            "data": data or {},
        })

    def log_error(
        self,
        *,
        step: str,
        err: BaseException,
        parent_span_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.tracer.emit({
            "ts": _utc_iso(),
            "event": "error",
            "trace_id": self.trace_id,
            "span_id": _new_id("ev_"),
            "parent_span_id": parent_span_id or self._root_span_id,
            "step": step,
            "error_type": type(err).__name__,
            "error_message": str(err),
            "stacktrace": traceback.format_exc(),
            "data": data or {},
        })

    @contextmanager
    def span(
        self,
        *,
        name: str,
        kind: str = "span",
        input: Optional[Dict[str, Any]] = None,
        parent_span_id: Optional[str] = None,
    ) -> Generator["Span", None, None]:
        sp = Span(
            trace=self,
            name=name,
            kind=kind,
            input=input or {},
            parent_span_id=parent_span_id or self._root_span_id,
        )
        sp.start()
        try:
            yield sp
            sp.end(status="ok")
        except Exception as e:
            sp.end(status="error", error=e)
            raise


class Span:
    def __init__(
        self,
        *,
        trace: Trace,
        name: str,
        kind: str,
        input: Dict[str, Any],
        parent_span_id: str,
    ):
        self.trace = trace
        self.name = name
        self.kind = kind
        self.input = input
        self.parent_span_id = parent_span_id

        self.span_id = _new_id("sp_")
        self._start_perf: Optional[float] = None
        self._ended: bool = False

    def start(self) -> None:
        self._start_perf = time.perf_counter()
        self.trace.tracer.emit({
            "ts": _utc_iso(),
            "event": "span_start",
            "trace_id": self.trace.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "input": self.input,
        })

    def end(
        self,
        *,
        status: str,
        output: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
    ) -> None:
        if self._ended:
            return
        self._ended = True

        dur = 0
        if self._start_perf is not None:
            dur = _ms_since(self._start_perf)

        payload: Dict[str, Any] = {
            "ts": _utc_iso(),
            "event": "span_end",
            "trace_id": self.trace.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind,
            "status": status,
            "duration_ms": dur,
            "output": output or {},
        }

        if error is not None:
            payload["error_type"] = type(error).__name__
            payload["error_message"] = str(error)

        self.trace.tracer.emit(payload)

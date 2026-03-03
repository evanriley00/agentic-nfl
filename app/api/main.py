from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.memory.store import MemoryStore
from app.agent.core import Agent
from app.observability import TRACER

app = FastAPI(title="Agentic NFL")

agent = Agent()
memory = MemoryStore(max_turns=10)


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


@app.middleware("http")
async def agent_trace_middleware(request: Request, call_next):
    trace = TRACER.start_trace(
        run_name="http_request",
        input_summary=f"{request.method} {request.url.path}",
        metadata={
            "query": dict(request.query_params),
            "client": request.client.host if request.client else None,
        },
    )

    request.state.trace = trace

    trace.run_start()

    try:
        with trace.span(
            name="fastapi_request",
            kind="span",
            input={"path": request.url.path, "method": request.method},
        ) as sp:
            response = await call_next(request)

            trace.log_event(
                event="http_response",
                data={"status_code": response.status_code},
                parent_span_id=sp.span_id,
            )

            response.headers["x-trace-id"] = trace.trace_id

        trace.run_end(status="ok", output_summary=f"status={response.status_code}")
        return response

    except Exception as e:
        trace.log_error(step="fastapi_request", err=e)
        trace.run_end(status="error", output_summary="unhandled_exception")
        raise


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    history = [{"role": m.role, "content": m.content} for m in memory.get(req.session_id)]
    memory.add(req.session_id, "user", req.message)

    trace = getattr(request.state, "trace", None)
    reply = agent.run(req.message, history, trace=trace, session_id=req.session_id)

    memory.add(req.session_id, "assistant", reply)
    return {"reply": reply}
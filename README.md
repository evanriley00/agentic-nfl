# Agentic NFL

A production-style agent framework that demonstrates deterministic tool routing,
external ML model orchestration, evidence retrieval from the web, and structured
trace logging for observability.

The system cleanly separates **prediction** (ML service) from **reasoning**
(agent layer), showcasing how an AI agent can call tools, aggregate evidence,
and produce explainable outputs with source attribution.

This repository focuses specifically on the agent architecture. The ML model
is treated as an external dependency, allowing the project to emphasize tool
orchestration, reasoning logic, and system design rather than model training.


## Architecture (high level)

User → FastAPI `/chat`  
→ Deterministic Router (choose tool)  
→ Tool Registry  
  - `wr_yards_predict` (calls external ML API)  
  - `web_fetch` (fetch page + extract evidence snippets)  
  - `analyze_wr_auto` (ML + evidence + critique)  
→ Response (+ `x-trace-id`)  
→ Trace written to `traces/agent_trace.jsonl`



## Requirements

- Python 3.12+
- Windows PowerShell (examples below)
- Environment variables:
  - `RECEIVER_YARDS_API_URL` (your ML API base URL)



## Quickstart

### 1) Create and activate venv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies
```powershell
pip install -r requirements.txt
```

### 3) Set ML API environment variable
```powershell
$env:RECEIVER_YARDS_API_URL = "http://127.0.0.1:8001"
```

### 4) Run the agent
```powershell
python -m uvicorn app.api.main:app --reload
```



## Demo

With the server running in one terminal:

```powershell
.\scripts\demo.ps1
```



## Example Manual Calls

### Predict
```powershell
iwr "http://127.0.0.1:8000/chat" -Method POST -ContentType "application/json" -Body '{"session_id":"demo","message":"predict Justin Jefferson vs CHI"}' -UseBasicParsing
```

### Analyze (Agentic Flow)
```powershell
iwr "http://127.0.0.1:8000/chat" -Method POST -ContentType "application/json" -Body '{"session_id":"demo","message":"analyze Justin Jefferson vs CHI"}' -UseBasicParsing
```



## Observability

Each response returns an `x-trace-id` header.

Trace logs are written to:

```
traces/agent_trace.jsonl
```

You will see:
- `route_decision`
- `tool_call`
- `tool_result`
- `http_response`



## Tests

```powershell
pytest -q
```



## Project Scope

This project demonstrates:
- deterministic routing
- tool orchestration
- evidence-based reasoning
- structured trace logging

It is an agent framework demo not a production betting model.
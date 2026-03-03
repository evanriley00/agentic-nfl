param(
  [string]$BaseUrl = "http://127.0.0.1:8000"
)

Write-Host "== Agentic NFL Demo =="

Write-Host "`n[1/3] Health check..."
$h = iwr "$BaseUrl/health" -UseBasicParsing
Write-Host $h.Content

Write-Host "`n[2/3] Predict (ML tool)..."
$p = iwr "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body '{"session_id":"demo","message":"predict Justin Jefferson vs CHI"}' -UseBasicParsing
Write-Host $p.Content
Write-Host ("trace_id=" + $p.Headers["x-trace-id"])

Write-Host "`n[3/3] Analyze (ML + web evidence + critique)..."
$a = iwr "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body '{"session_id":"demo","message":"analyze Justin Jefferson vs CHI"}' -UseBasicParsing
Write-Host $a.Content
Write-Host ("trace_id=" + $a.Headers["x-trace-id"])

Write-Host "`nTrace logs:"
Write-Host "  .\traces\agent_trace.jsonl"

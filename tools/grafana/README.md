# Sovereign Vision · Grafana + Prometheus

Out-of-the-box observability for the constitutional firewall.

## Quick start (60 seconds)

```bash
# 1. Start the Sovereign Vision API
uvicorn sovereign.server:app --host 127.0.0.1 --port 8765

# 2. Run Prometheus pointed at /metrics
prometheus --config.file=tools/grafana/prometheus.yml

# 3. In Grafana:
#    - Add datasource: Prometheus, URL http://localhost:9090, uid `sovereign-prom`
#    - Import dashboard from `tools/grafana/sovereign-vision-dashboard.json`
```

The dashboard ships with:

- Live FPS, inference latency, firewall latency stat panels
- Status mix donut chart (CLEAR / ESCALATED / BLOCKED)
- Inference + firewall latency time series
- Total PII redactions, total frames, rules-per-frame

## Metric reference

| Metric | Type | Description |
|---|---|---|
| `sovereign_fps` | gauge | Frames per second |
| `sovereign_inference_latency_ms` | gauge | Mean inference latency (ms) |
| `sovereign_firewall_latency_ms` | gauge | Mean firewall processing (ms) |
| `sovereign_total_frames` | counter | Frames processed since start |
| `sovereign_total_rules_fired` | counter | Constitutional rules fired |
| `sovereign_total_redactions` | counter | PII redactions performed |
| `sovereign_status_count{status=...}` | counter | Frames per status (CLEAR/ESCALATED/BLOCKED) |

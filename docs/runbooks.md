# Operational Alert Runbooks

This document outlines troubleshooting steps and root cause analysis procedures for each alert configured in this observability stack.

---

## 1. Alert: `TargetDown`

### Severity: `CRITICAL`
- **Condition**: `up{job="sample-app"} == 0` for 30 seconds
- **Summary**: Target `sample-app:8000` is unreachable or stopped responding to Prometheus scrapes.

### Investigation Steps
1. **Check Container Status**:
   ```bash
   docker compose ps sample-app
   ```
2. **Inspect Process Exit Codes & Logs**:
   ```bash
   docker compose logs --tail=50 sample-app
   ```
3. **Verify Network Connectivity**:
   Test if the container is listening on port 8000:
   ```bash
   curl -I http://localhost:8000/health
   ```
4. **Resolution**:
   - If the container crashed, restart it: `docker compose restart sample-app`
   - Check if an Out Of Memory (OOM) killer killed the container: `docker inspect sample-app --format '{{json .State}}'`

---

## 2. Alert: `HighErrorRate`

### Severity: `CRITICAL`
- **Condition**: HTTP 5xx error rate > 10% over 1 minute
- **Summary**: The sample API is returning an unacceptable volume of server errors.

### Investigation Steps
1. **Open Grafana Logs Correlation Dashboard**:
   Navigate to [http://localhost:3000/d/logs-correlation-dashboard](http://localhost:3000/d/logs-correlation-dashboard).
2. **Inspect LogQL Filtered Errors**:
   Execute LogQL query:
   ```logql
   {job=~"sample-app.*"} | json | status_code >= 500
   ```
3. **Analyze Stack Traces**:
   Look for `error_type` or exception details in the JSON log payload (e.g., `DatabaseTimeoutException`).
4. **Mitigation**:
   - Check downstream database/dependency status.
   - Scale service replicas if errors are caused by thread exhaustion.
   - Roll back recent deployment if errors correlate with a specific release tag.

---

## 3. Alert: `HighP95Latency`

### Severity: `WARNING`
- **Condition**: P95 response duration > 0.5s (500ms) over 1 minute
- **Summary**: 95% of users are experiencing high latency.

### Investigation Steps
1. **Open Grafana RED Dashboard**:
   Navigate to [http://localhost:3000/d/red-metrics-dashboard](http://localhost:3000/d/red-metrics-dashboard).
2. **Identify Slow Endpoints**:
   Check the "Request Rate by Endpoint" panel against latency percentiles to isolate which endpoint is degrading:
   ```promql
   histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, endpoint))
   ```
3. **Correlate with Logs**:
   In Loki, query requests exceeding 500ms:
   ```logql
   {job=~"sample-app.*"} | json | duration_seconds > 0.5
   ```
4. **Mitigation**:
   - Investigate long-running queries or external network calls.
   - Adjust worker threads or increase horizontal replicas.

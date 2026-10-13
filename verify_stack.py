import urllib.request
import json
import sys

def test_endpoint(name, url, expected_code=200, auth=None):
    try:
        req = urllib.request.Request(url)
        if auth:
            import base64
            auth_header = base64.b64encode(auth.encode()).decode()
            req.add_header("Authorization", f"Basic {auth_header}")
        with urllib.request.urlopen(req, timeout=5) as res:
            content = res.read().decode('utf-8', errors='ignore')
            status = res.status
            passed = (status == expected_code)
            print(f"[{'PASS' if passed else 'FAIL'}] {name} ({url}) -> Status: {status}")
            return passed, content
    except Exception as e:
        print(f"[FAIL] {name} ({url}) -> Error: {e}")
        return False, str(e)

print("=" * 60)
print("OBSERVABILITY STACK VERIFICATION REPORT")
print("=" * 60)

# 1. Sample App
p, c = test_endpoint("Sample App Health", "http://localhost:8000/health")
p, c = test_endpoint("Sample App Metrics Exposition", "http://localhost:8000/metrics")
if "http_requests_total" in c:
    print("  -> Metrics exposed: http_requests_total PRESENT")
if "ecommerce_orders_processed_total" in c:
    print("  -> Business KPI: ecommerce_orders_processed_total PRESENT")

# 2. Prometheus
p, c = test_endpoint("Prometheus Health", "http://localhost:9090/-/healthy")
p, c = test_endpoint("Prometheus Scrape Targets API", "http://localhost:9090/api/v1/targets")
if p:
    data = json.loads(c)
    targets = data.get("data", {}).get("activeTargets", [])
    for t in targets:
        job = t.get("labels", {}).get("job", "unknown")
        health = t.get("health", "unknown")
        print(f"  -> Scrape Target '{job}' state: {health.upper()}")

# 3. Alertmanager
p, c = test_endpoint("Alertmanager Health", "http://localhost:9093/-/healthy")

# 4. Loki
p, c = test_endpoint("Loki Readiness", "http://localhost:3100/ready")
p, c = test_endpoint("Loki Query API", "http://localhost:3100/loki/api/v1/query?query=%7Bjob%3D~%22sample-app.*%22%7D")
if p:
    data = json.loads(c)
    streams = data.get("data", {}).get("result", [])
    print(f"  -> Loki Streams Ingested for sample-app: {len(streams)} stream(s)")

# 5. Promtail
p, c = test_endpoint("Promtail Readiness", "http://localhost:9080/ready")

# 6. Grafana
p, c = test_endpoint("Grafana Health", "http://localhost:3000/api/health")
p, c = test_endpoint("Grafana Provisioned Datasources", "http://localhost:3000/api/datasources", auth="admin:admin")
if p:
    ds = json.loads(c)
    for d in ds:
        print(f"  -> Datasource: '{d.get('name')}' (Type: {d.get('type')}, URL: {d.get('url')})")

p, c = test_endpoint("Grafana Provisioned Dashboards", "http://localhost:3000/api/search?type=dash-db", auth="admin:admin")
if p:
    dashboards = json.loads(c)
    for d in dashboards:
        print(f"  -> Dashboard: '{d.get('title')}' (UID: {d.get('uid')})")

print("=" * 60)

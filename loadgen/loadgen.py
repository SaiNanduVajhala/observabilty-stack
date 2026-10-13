import argparse
import os
import random
import sys
import time
import urllib.request
import urllib.error
import json

TARGET_URL = os.getenv("TARGET_URL", "http://sample-app:8000")


def send_request(endpoint, method="GET", data=None):
    url = f"{TARGET_URL.rstrip('/')}{endpoint}"
    req = urllib.request.Request(url, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
        body = json.dumps(data).encode("utf-8")
    else:
        body = None

    try:
        with urllib.request.urlopen(req, data=body, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)


def run_normal_traffic(duration_sec=30):
    print(f"[*] Running NORMAL steady traffic for {duration_sec}s...")
    start = time.time()
    while time.time() - start < duration_sec:
        # 70% Orders, 20% Root/Health, 5% slow, 5% error
        roll = random.random()
        if roll < 0.70:
            order_data = {
                "payment_method": random.choice(["credit_card", "paypal", "apple_pay", "crypto"]),
                "amount": round(random.uniform(20.0, 450.0), 2),
                "currency": "USD"
            }
            status, _ = send_request("/api/orders", method="POST", data=order_data)
        elif roll < 0.90:
            status, _ = send_request("/health")
        elif roll < 0.95:
            status, _ = send_request("/api/slow?delay=0.1")
        else:
            status, _ = send_request("/api/error?rate=0.2")

        time.sleep(random.uniform(0.1, 0.4))


def run_error_spike(duration_sec=45):
    print(f"[!] TRIGGERING ALERT: High 5xx Error Rate Spike for {duration_sec}s...")
    start = time.time()
    while time.time() - start < duration_sec:
        # 80% 500 errors, 20% normal traffic
        if random.random() < 0.85:
            status, _ = send_request("/api/error?rate=1.0")
        else:
            status, _ = send_request("/api/orders", method="POST", data={"amount": 50})
        time.sleep(0.08)
    print("[+] Error spike completed.")


def run_latency_spike(duration_sec=45):
    print(f"[!] TRIGGERING ALERT: High P95 Latency Spike (>0.5s) for {duration_sec}s...")
    start = time.time()
    while time.time() - start < duration_sec:
        delay = round(random.uniform(0.8, 1.8), 2)
        status, _ = send_request(f"/api/slow?delay={delay}")
        time.sleep(0.05)
    print("[+] Latency spike completed.")


def main():
    parser = argparse.ArgumentParser(description="Observability Stack Load Generator")
    parser.add_argument(
        "--scenario",
        choices=["normal", "error-spike", "latency-spike", "demo-loop"],
        default=os.getenv("SCENARIO", "demo-loop"),
        help="Traffic scenario to generate"
    )
    args = parser.parse_args()

    print(f"=== Load Generator Starting ===")
    print(f"Target: {TARGET_URL}")
    print(f"Scenario: {args.scenario}")

    # Wait for target app to be healthy
    print("[*] Waiting for sample app to become healthy...")
    retries = 30
    while retries > 0:
        status, _ = send_request("/health")
        if status == 200:
            print("[+] Sample app is healthy and reachable!")
            break
        time.sleep(2)
        retries -= 1

    if args.scenario == "normal":
        while True:
            run_normal_traffic(duration_sec=30)
    elif args.scenario == "error-spike":
        run_error_spike(duration_sec=60)
    elif args.scenario == "latency-spike":
        run_latency_spike(duration_sec=60)
    elif args.scenario == "demo-loop":
        print("[*] Running continuous Demo Loop (steady traffic + periodic alert spikes)...")
        while True:
            # 1. Normal traffic for 40 seconds
            run_normal_traffic(duration_sec=40)
            # 2. Latency spike for 40 seconds (triggers HighP95Latency alert)
            run_latency_spike(duration_sec=40)
            # 3. Normal traffic for 20 seconds
            run_normal_traffic(duration_sec=20)
            # 4. Error spike for 40 seconds (triggers HighErrorRate alert)
            run_error_spike(duration_sec=40)


if __name__ == "__main__":
    main()

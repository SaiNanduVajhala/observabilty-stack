import logging
import random
import sys
import time
from flask import Flask, Response, jsonify, request
from pythonjsonlogger import jsonlogger
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

# ---------------------------------------------------------
# 1. Structured JSON Logging Setup
# ---------------------------------------------------------
logger = logging.getLogger("sample-app")
logger.setLevel(logging.INFO)

# Log to stdout in structured JSON format
log_handler = logging.StreamHandler(sys.stdout)
formatter = jsonlogger.JsonFormatter(
    "%(asctime)s %(levelname)s %(name)s %(message)s"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)

# Also write to shared log directory if available for resilient Promtail volume mounting
import os
log_file = os.getenv("LOG_FILE_PATH", "/var/log/app/app.log")
try:
    log_dir = os.path.dirname(log_file)
    if log_dir and os.path.exists(log_dir):
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
except Exception:
    pass

logger.propagate = False

app = Flask(__name__)

# ---------------------------------------------------------
# 2. Prometheus Metrics Definition
# ---------------------------------------------------------
# Request Counter (Rate & Errors)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"],
)

# Request Latency Histogram (Duration)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0),
)

# Error Counter
HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total",
    "Total HTTP errors (status >= 400)",
    ["method", "endpoint", "status"],
)

# Custom Business Metric: Orders processed and total revenue
ORDERS_PROCESSED_TOTAL = Counter(
    "ecommerce_orders_processed_total",
    "Total e-commerce orders placed",
    ["payment_method", "currency"],
)

ORDER_REVENUE_TOTAL = Counter(
    "ecommerce_order_revenue_total",
    "Total revenue from e-commerce orders",
    ["currency"],
)

# ---------------------------------------------------------
# 3. Request Interceptors for Metrics & Structured Logs
# ---------------------------------------------------------
@app.before_request
def start_timer():
    request._start_time = time.time()


@app.after_request
def record_metrics_and_log(response):
    # Skip tracking the /metrics endpoint itself to avoid recursion noise
    if request.path == "/metrics":
        return response

    duration = time.time() - getattr(request, "_start_time", time.time())
    status_code = str(response.status_code)
    endpoint = request.endpoint or request.path

    # Record metrics
    HTTP_REQUESTS_TOTAL.labels(
        method=request.method, endpoint=endpoint, status=status_code
    ).inc()

    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=request.method, endpoint=endpoint
    ).observe(duration)

    if response.status_code >= 400:
        HTTP_ERRORS_TOTAL.labels(
            method=request.method, endpoint=endpoint, status=status_code
        ).inc()

    # Emit structured JSON log
    log_data = {
        "service": "sample-api",
        "method": request.method,
        "path": request.path,
        "endpoint": endpoint,
        "status_code": response.status_code,
        "duration_seconds": round(duration, 4),
        "ip": request.remote_addr,
    }

    if response.status_code >= 500:
        logger.error("Request failed with server error", extra=log_data)
    elif response.status_code >= 400:
        logger.warning("Request completed with client error", extra=log_data)
    else:
        logger.info("Request completed successfully", extra=log_data)

    return response


# ---------------------------------------------------------
# 4. API Endpoints
# ---------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "sample-api", "version": "1.0.0"}), 200


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Observability Stack Sample API",
        "endpoints": {
            "/health": "Service health check",
            "/metrics": "Prometheus metrics exposition endpoint",
            "/api/orders": "POST - Place order (custom business metric)",
            "/api/slow": "GET - Intentionally slow response (triggers p95 alert)",
            "/api/error": "GET - Intentionally returns 500 error (triggers error rate alert)",
        }
    }), 200


@app.route("/api/orders", methods=["POST"])
def place_order():
    """Simulates placing an order to demonstrate custom business metrics."""
    data = request.get_json(silent=True) or {}
    payment_method = data.get("payment_method", random.choice(["credit_card", "paypal", "apple_pay", "crypto"]))
    amount = float(data.get("amount", round(random.uniform(15.0, 350.0), 2)))
    currency = data.get("currency", "USD")

    # Increment custom business metrics
    ORDERS_PROCESSED_TOTAL.labels(payment_method=payment_method, currency=currency).inc()
    ORDER_REVENUE_TOTAL.labels(currency=currency).inc(amount)

    order_id = f"ord-{random.randint(10000, 99999)}"
    logger.info(
        f"Order {order_id} placed successfully",
        extra={
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "action": "place_order"
        }
    )

    return jsonify({
        "order_id": order_id,
        "status": "confirmed",
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
    }), 201


@app.route("/api/slow", methods=["GET"])
def slow_endpoint():
    """Intentionally delays response to test p95 latency alerts."""
    delay = float(request.args.get("delay", random.uniform(0.7, 1.6)))
    time.sleep(delay)
    return jsonify({
        "message": f"Processed after artificial delay of {delay:.2f}s",
        "delay_seconds": round(delay, 2),
    }), 200


@app.route("/api/error", methods=["GET"])
def error_endpoint():
    """Intentionally fails or simulates unpredictable failure rates."""
    rate = float(request.args.get("rate", 1.0))
    if random.random() <= rate:
        logger.error(
            "Unhandled simulated database connection timeout",
            extra={
                "error_type": "DatabaseTimeoutException",
                "component": "order_repository",
                "simulated": True
            }
        )
        return jsonify({
            "error": "InternalServerError",
            "message": "Simulated database connection timeout",
            "code": 500
        }), 500

    return jsonify({"status": "success", "message": "Call succeeded unexpectedly!"}), 200


@app.route("/metrics", methods=["GET"])
def metrics():
    """Exposes Prometheus metrics in OpenMetrics/Prometheus text format."""
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

from prometheus_client import Counter, Gauge

# 1. Track how many times the math node infers missing taxes
invoice_healer_triggered_total = Counter(
    "invoice_healer_triggered_total",
    "Total number of times the math node inferred missing taxes (SGST/CGST)"
)

# 2. Track the total financial gap of failed invoices
invoice_unreconciled_value = Gauge(
    "invoice_unreconciled_value",
    "The total mathematical gap (₹) of invoices that failed reconciliation"
)

# 3. Track infinite loop prevention events (Circuit Breaker)
circuit_breaker_tripped_total = Counter(
    "circuit_breaker_tripped_total",
    "Total number of times the LangGraph circuit breaker was tripped to prevent infinite loops"
)

# 4. Track the total count of retries across all extractions
invoice_extraction_retries_total = Counter(
    "invoice_extraction_retries_total",
    "Total number of times the AI extraction was retried due to validation failures"
)

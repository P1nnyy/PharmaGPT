from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Watch out for missed decimal points. If MRP is > 1000, check if it should be divided by 100 (e.g. 16500 -> 165.00).",
    "CRITICAL: Batch Numbers like 'Batch 123' and '123' are the SAME. Merge them.",
    "CRITICAL: Do NOT list the same item twice. If Product and Batch match, SUM them."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Decimal & Dedupe Rules.")

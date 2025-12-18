from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Column Selection: If you see 'Total' (often Gross) and 'Amount' (often Net), prefer 'Amount'.",
    "CRITICAL: 'Total Cost' mismatch is often due to picking 'Taxable Value' or 'Gross Total' instead of 'Net Amount'. Pick the lowest final column."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Column Selection Rule.")

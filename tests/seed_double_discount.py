from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Do NOT extract 'Total Scheme Discount' as Global Discount. It is usually a summary of line items. Only extract 'Cash Discount' or 'Bill Discount'.",
    "CRITICAL: If Quantity text is '0 0 5', extract 5. Ignore zeros."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Double Discount Rule.")

from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: 'Amount' must be NET Amount (Tax Inclusive). Do NOT extract 'Taxable Value'."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Net Amount Rule.")

from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Perform a Sanity Check: Does 'Qty * Rate' approx equal 'Amount'? If not, check for missing decimal points in Rate or Amount."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Consistency Rule.")

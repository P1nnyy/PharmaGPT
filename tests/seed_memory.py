from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Do NOT extract 8-digit HSN codes (e.g. 30043110) as Expiry Date.",
    "CRITICAL: Do NOT extract 4-digit HSN codes (e.g. 3004) as Expiry Date.",
    "CRITICAL: Quantity is usually small (< 50). Do not confuse Rate/MRP (e.g. 100, 200) with Qty."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Seeded.")

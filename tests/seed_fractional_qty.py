from src.services.mistake_memory import MEMORY

rules = [
    "CRITICAL: Quantity must be an INTEGER (Whole Packs). If you see '1.84', it means '2'. Round decimals UP.",
    "CRITICAL: Amount matches the Quantity. If you extract 1.84 as 2, ensure you extract the Amount that corresponds to it (or keep original Amount and let Solver adjust Rate)."
]

for r in rules:
    MEMORY.add_rule(r)

print("Memory Updated with Fractional Rounding Rule.")

from src.services.mistake_memory import MEMORY

from src.domain.constants import EXTRACTION_RULES

for r in EXTRACTION_RULES:
    MEMORY.add_rule(r)

print("Memory Seeded.")

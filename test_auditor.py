import asyncio
from src.workflow.nodes.auditor import audit_extraction

state = {
    "image_path": "fake.jpg",
    "line_item_fragments": [{"Product": "Test", "Qty": 1, "Rate": 100, "Amount": 100}],
    "global_modifiers": {"Supplier_Name": "Apollo Pharmacy"}
}
result = asyncio.run(audit_extraction(state))
print(result)

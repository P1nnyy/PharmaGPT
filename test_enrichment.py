import asyncio
import os
import json
from src.workflow.nodes.researcher import enrich_line_items

async def test():
    state = {
        "line_items": [
            {
                "Product": "Ondero Met 2.5/1000 M",
                "Standard_Item_Name": "Ondero Met 2.5/1000 M",
                "Manufacturer": "Unknown",
                "Salt": None
            }
        ]
    }
    print("Testing enrichment for Ondero Met...")
    result = await enrich_line_items(state)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(test())

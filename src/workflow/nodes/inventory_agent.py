from typing import Dict, Any
from src.workflow.state import SupplyChainState
from src.services.database import get_db_driver
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

async def analyze_inventory(state: SupplyChainState) -> Dict[str, Any]:
    """
    Inventory Agent: Analyzes Neo4j stock levels to prevent stockouts.
    Role: Inventory Agent. Goal: Prevent stockouts. Guardrails: Adhere to strict healthcare compliance.
    """
    tenant_id = state.get("tenant_id")
    logger.info(f"Inventory Agent: Analyzing stock for tenant {tenant_id}")
    
    driver = get_db_driver()
    query = """
    MATCH (gp:GlobalProduct {tenant_id: $tenant_id})
    WHERE gp.opening_stock <= gp.min_stock
    RETURN gp.name as product_name, gp.opening_stock as current_stock, gp.min_stock as threshold
    """
    
    alerts = []
    try:
        with driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            for record in result:
                alerts.append({
                    "product": record["product_name"],
                    "status": "CRITICAL_STOCKOUT_RISK",
                    "details": f"Current stock ({record['current_stock']}) is below threshold ({record['threshold']})"
                })
    except Exception as e:
        logger.error(f"Inventory Agent Error: {e}")

    return {"inventory_alerts": alerts}

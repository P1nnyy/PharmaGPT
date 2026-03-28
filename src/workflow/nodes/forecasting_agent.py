from typing import Dict, Any
from src.workflow.state import SupplyChainState
from src.services.database import get_db_driver
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

async def forecast_demand(state: SupplyChainState) -> Dict[str, Any]:
    """
    Demand Forecasting Agent: Analyzes historical purchase data to predict future volumes.
    Goal: Predict required volumes for the next 90 days.
    """
    tenant_id = state.get("tenant_id")
    logger.info(f"Forecasting Agent: Analyzing historical data for tenant {tenant_id}")
    
    driver = get_db_driver()
    # Query for last 6 months of purchase volume per product
    query = """
    MATCH (i:Invoice {tenant_id: $tenant_id, status: 'CONFIRMED'})-[:CONTAINS]->(li:Line_Item)
    WHERE i.created_at > timestamp() - (180 * 24 * 60 * 60 * 1000)
    RETURN li.product_name as product_name, sum(li.quantity) as total_volume
    """
    
    forecasts = []
    try:
        with driver.session() as session:
            result = session.run(query, tenant_id=tenant_id)
            for record in result:
                avg_monthly = record["total_volume"] / 6
                prediction_90d = round(avg_monthly * 3, 2)
                forecasts.append({
                    "product": record["product_name"],
                    "predicted_90d_volume": prediction_90d,
                    "confidence": "MEDIUM (Historical Average)"
                })
    except Exception as e:
        logger.error(f"Forecasting Agent Error: {e}")

    return {"demand_forecasts": forecasts}

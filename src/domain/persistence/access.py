from typing import Dict, Any
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def upsert_user(driver, user_data: Dict[str, Any]):
    """
    Creates or updates a User node based on Google OAuth data.
    """
    query = """
    MERGE (u:User {email: $email})
    SET u.google_id = $google_id,
        u.name = $name,
        u.picture = $picture,
        u.updated_at = timestamp()
    RETURN u
    """
    with driver.session() as session:
        session.execute_write(lambda tx: tx.run(query, 
                    email=user_data.get("email"),
                    google_id=user_data.get("google_id"),
                    name=user_data.get("name"),
                    picture=user_data.get("picture")))

def _merge_supplier_tx(tx, name: str, details: Dict[str, Any], user_email: str, tenant_id: str):
    query = """
    MATCH (u:User {email: $user_email})
    MERGE (s:Supplier {name: $name, tenant_id: $tenant_id})
    
    // Create management relationship if not exists
    MERGE (u)-[:MANAGES_SUPPLIER]->(s)
    
    SET s.address = $address,
        s.gstin = $gstin,
        s.dl_no = $dl_no,
        s.phone = $phone,
        s.email = $email,
        s.updated_at = timestamp()
    """
    tx.run(query, 
           user_email=user_email,
           name=name,
           tenant_id=tenant_id,
           address=details.get("Address"),
           gstin=details.get("GSTIN"),
           dl_no=details.get("DL_No"),
           phone=details.get("Phone_Number"),
           email=details.get("Email")
    )

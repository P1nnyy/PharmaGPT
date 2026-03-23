import logging
from src.services.database import get_db_driver

logger = logging.getLogger(__name__)

# --- ITEM CATEGORIES ---
def create_item_category(category_name: str, base_unit: str = "Unit", supports_atomic: bool = False, description: str = "", parent_name: str = None, user_email: str = None) -> dict:
    """Creates a new ItemCategory node and optionally links it to a parent. If user_email provided, assigns ownership."""
    
    # Base query for creating/updating the node
    query = """
    MERGE (c:ItemCategory {name: $name})
    SET c.description = $description,
        c.base_unit = $base_unit,
        c.supports_atomic = $supports_atomic,
        c.created_at = coalesce(c.created_at, datetime()),
        c.is_default = coalesce(c.is_default, false)
    """
    
    # Add relationship logic if a parent is specified
    if parent_name:
        query += """
        WITH c
        MATCH (p:ItemCategory {name: $parent_name})
        MERGE (p)-[:CHILD]->(c)
        """
        
    if user_email:
        query += """
        WITH c
        MERGE (u:User {email: $email})
        MERGE (u)-[:OWNS_CATEGORY]->(c)
        """
        
    query += "RETURN c { .name, .description, .base_unit, .supports_atomic, .created_at, is_default: c.is_default } as category"

    db = get_db_driver()
    try:
        params = {
            "name": category_name.strip(), 
            "description": description,
            "base_unit": base_unit,
            "supports_atomic": supports_atomic
        }
        if parent_name:
            params["parent_name"] = parent_name.strip()
        if user_email:
            params["email"] = user_email
            
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, **params).single())
            return record["category"] if record else None
    except Exception as e:
        logger.error(f"Error creating ItemCategory: {e}")
        raise e

def get_all_item_categories() -> list:
    """Fetches all ItemCategory nodes, including their parent if any."""
    query = """
    MATCH (c:ItemCategory)
    OPTIONAL MATCH (p:ItemCategory)-[:CHILD]->(c)
    RETURN c { .name, .description, .created_at, parent_name: p.name, is_default: coalesce(c.is_default, false) } as category
    ORDER BY c.name
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            return session.execute_read(lambda tx: [record["category"] for record in tx.run(query)])
    except Exception as e:
        logger.error(f"Error fetching ItemCategories: {e}")
        return []

def get_user_categories(user_email: str) -> list:
    """Fetches all default categories plus user-created ones, including user config."""
    # We fetch:
    # 1. All categories (either default or owned by user)
    # 2. Any config the user has set on them (e.g. supports_atomic_sizing)
    query = """
    MATCH (u:User {email: $email})
    MATCH (c:ItemCategory)
    WHERE coalesce(c.is_default, false) = true OR (u)-[:OWNS_CATEGORY]->(c)
    
    OPTIONAL MATCH (p:ItemCategory)-[:CHILD]->(c)
    OPTIONAL MATCH (u)-[conf:CONFIGURES_CATEGORY]->(c)
    
    RETURN c { 
        .name, 
        .description, 
        .created_at, 
        parent_name: p.name,
        is_default: coalesce(c.is_default, false),
        supports_atomic_sizing: coalesce(conf.supports_atomic_sizing, false),
        units: coalesce(conf.units, [])
    } as category
    ORDER BY c.name
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            return session.execute_read(lambda tx: [record["category"] for record in tx.run(query, email=user_email)])
    except Exception as e:
        logger.error(f"Error fetching user categories: {e}")
        return []

def configure_category(user_email: str, category_name: str, config_updates: dict) -> dict:
    """Upserts a user's configuration for a specific category."""
    query = """
    MATCH (u:User {email: $email})
    MATCH (c:ItemCategory {name: $category_name})
    
    MERGE (u)-[conf:CONFIGURES_CATEGORY]->(c)
    SET conf += $updates,
        conf.updated_at = datetime()
        
    RETURN {
        name: c.name,
        supports_atomic_sizing: coalesce(conf.supports_atomic_sizing, false),
        units: coalesce(conf.units, [])
    } as config
    """
    db = get_db_driver()
    try:
        # Sanitize updates to only allow known configuration keys
        updates = {}
        if "supports_atomic_sizing" in config_updates:
            updates["supports_atomic_sizing"] = config_updates["supports_atomic_sizing"]
        if "units" in config_updates:
            updates["units"] = config_updates["units"]
            
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, email=user_email, category_name=category_name, updates=updates).single())
            return record["config"] if record else None
    except Exception as e:
        logger.error(f"Error configuring category: {e}")
        return None

def seed_default_categories():
    """Seeds default categories like Tablet and Bottle, and cleans up legacy ones."""
    defaults = [
        {"name": "Tablet", "description": "Solid dosage form"},
        {"name": "Capsule", "description": "Capsule dosage form"},
        {"name": "Bottle", "description": "Liquid container"},
        {"name": "Vial", "description": "Vial container"},
        {"name": "Injection", "description": "Injectable form"},
        {"name": "Tube", "description": "Tube container"},
        {"name": "Sachet", "description": "Sachet pack"},
    ]
    
    valid_names = [d["name"] for d in defaults]
    
    query_merge = """
    UNWIND $categories AS cat
    MERGE (c:ItemCategory {name: cat.name})
    SET c.description = cat.description,
        c.is_default = true,
        c.created_at = coalesce(c.created_at, datetime())
    """
    
    query_cleanup = """
    MATCH (c:ItemCategory)
    WHERE coalesce(c.is_default, false) = true AND NOT c.name IN $valid_names
    DETACH DELETE c
    """
    
    db = get_db_driver()
    try:
        if db:
            def _seed_tx(tx):
                tx.run(query_merge, categories=defaults)
                tx.run(query_cleanup, valid_names=valid_names)

            with db.session() as session:
                session.execute_write(_seed_tx)
                logger.info("Default categories seeded and legacy defaults cleaned up successfully.")
    except Exception as e:
        logger.error(f"Error seeding default categories: {e}")

def delete_item_category(category_name: str) -> bool:
    """Deletes an ItemCategory node and reassigns its children to its parent, or orphans them."""
    # DETACH DELETE automatically removes all relationships (including :CHILD)
    query = """
    MATCH (c:ItemCategory {name: $name})
    DETACH DELETE c
    RETURN count(c) as deleted_count
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, name=category_name).single())
            return record["deleted_count"] > 0 if record else False
    except Exception as e:
        logger.error(f"Error deleting ItemCategory: {e}")
        return False

# --- CONFIGURATION / ROLES (Future Expansion) ---
# Placeholder for role definitions if they ever need dynamic Neo4j storage.
# Currently roles are usually handled by auth providers or JWTs, but if 
# we need complex role-based graph permissions, they drop in here.

def create_system_role(role_name: str, permissions: list) -> dict:
    """Creates a conceptual Role node (if needed by frontend)."""
    query = """
    MERGE (r:Role {name: $name})
    SET r.permissions = $permissions
    RETURN r { .name, .permissions } as role
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, name=role_name, permissions=permissions).single())
            return record["role"] if record else None
    except Exception as e:
        logger.error(f"Error creating SystemRole: {e}")
        raise e

def get_all_system_roles() -> list:
    """Fetches all custom system roles."""
    query = """
    MATCH (r:Role)
    RETURN r { .name, .permissions } as role
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            return session.execute_read(lambda tx: [record["role"] for record in tx.run(query)])
    except Exception as e:
        logger.error(f"Error fetching SystemRoles: {e}")
        return []

def assign_user_role(user_email: str, role_name: str) -> bool:
    """Assigns a Role to a User"""
    query = """
    MATCH (u:User {email: $email})
    MATCH (r:Role {name: $role_name})
    MERGE (u)-[:HAS_ROLE]->(r)
    RETURN u, r
    """
    db = get_db_driver()
    try:
        with db.session() as session:
            record = session.execute_write(lambda tx: tx.run(query, email=user_email, role_name=role_name).single())
            return True if record else False
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        return False

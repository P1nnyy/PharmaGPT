
from neo4j import GraphDatabase
from src.core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
from src.utils.logging_config import get_logger

logger = get_logger("database")

driver = None

def connect_db():
    """
    Initializes the Neo4j driver.
    """
    global driver
    if driver:
        return driver
        
    try:
        # Added keep_alive and optimized timeouts for cloud environments (Aura)
        driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            max_connection_lifetime=180, # 3 mins (stay below Aura's 5 min idle timeout)
            max_connection_pool_size=50,
            connection_timeout=30.0,
            liveness_check_timeout=30.0, # Verify connection if idle for > 30s
            keep_alive=True
        )
        # We NO LONGER call verify_connectivity() here as it blocks the event loop
        # The driver will lazily connect on first query.
        logger.info("Neo4j driver initialized (Lazy Connection).")
        
        # We will keep the index initialization but it will be run lazily as well or 
        # we can just skip it here if it's already done.
        return driver
        
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j driver: {e}")
        driver = None
        return None

def get_db_driver():
    """
    Returns the active Neo4j driver instance.
    """
    global driver
    if not driver:
        return connect_db()
    return driver

def close_db():
    """
    Closes the Neo4j driver.
    """
    if driver:
        driver.close()
        logger.info("Neo4j driver closed.")

def init_vector_index(driver):
    """
    Creates Vector Indexes for Invoice Examples and HSN Codes.
    Run this on startup.
    moved from src/persistence.py
    """
    # 1. Invoice Examples Index
    q1 = """
    CREATE VECTOR INDEX invoice_examples_index IF NOT EXISTS
    FOR (n:InvoiceExample)
    ON (n.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """
    
    # 2. HSN Vector Index
    q2 = """
    CREATE VECTOR INDEX hsn_vector_index IF NOT EXISTS
    FOR (n:HSN)
    ON (n.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """
    
    # 3. Product Master Index
    q3 = """
    CREATE VECTOR INDEX product_index IF NOT EXISTS
    FOR (n:Product)
    ON (n.embedding)
    OPTIONS {indexConfig: {
      `vector.dimensions`: 768,
      `vector.similarity_function`: 'cosine'
    }}
    """
    
    try:
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run(q1))
            logger.info("Vector Index 'invoice_examples_index' initialization checked.")
            
            session.execute_write(lambda tx: tx.run(q2))
            logger.info("Vector Index 'hsn_vector_index' initialization checked.")

            session.execute_write(lambda tx: tx.run(q3))
            logger.info("Vector Index 'product_index' initialization checked.")
    except Exception as e:
        logger.error(f"Failed to create Vector Indexes: {e}")

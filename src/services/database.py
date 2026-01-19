
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
    try:
        # Added keep_alive and max_connection_lifetime to prevent 'defunct connection' errors after idle time
        driver = GraphDatabase.driver(
            NEO4J_URI, 
            auth=(NEO4J_USER, NEO4J_PASSWORD),
            max_connection_lifetime=200, # Refresh connections every 3.5 mins approx
            keep_alive=True
        )
        driver.verify_connectivity()
        logger.info("Connected to Neo4j.")
        
        # Initialize Vector Index on Startup
        init_vector_index(driver)
        
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e} - Application will start in partial mode (No DB)")
        driver = None

def get_db_driver():
    """
    Returns the active Neo4j driver instance.
    Includes auto-reconnection logic for stale connections.
    """
    global driver
    if driver:
        try:
            # lightweight connectivity check is expensive on flaky networks
            # driver.verify_connectivity() 
            return driver
        except Exception as e:
            logger.warning(f"Neo4j Connection Defunct ({e}). Reconnecting...")
            try:
                driver.close()
            except:
                pass
            driver = None

    # Reconnect if None or defunct
    connect_db()
    return driver

def close_db():
    """
    Closes the Neo4j driver.
    """
    global driver
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
    
    try:
        with driver.session() as session:
            session.run(q1)
            logger.info("Vector Index 'invoice_examples_index' initialization checked.")
            
            session.run(q2)
            logger.info("Vector Index 'hsn_vector_index' initialization checked.")
    except Exception as e:
        logger.error(f"Failed to create Vector Indexes: {e}")

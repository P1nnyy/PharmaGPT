from src.services.database import get_db_driver
from src.services.embeddings import generate_embedding
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def search_hsn_neo4j(description: str, threshold: float = 0.85) -> str:
    """
    Searches for HSN code in Neo4j using vector similarity.
    Assumes (:HSN) nodes have a 'description' and 'embedding' property.
    And a vector index named 'hsn_vector_index'.
    """
    if not description:
        return None
        
    driver = get_db_driver()
    if not driver:
        # Fallback silently or log warning
        return None
        
    try:
        embedding = generate_embedding(description)
        if not embedding:
            return None
            
        # Query for nearest neighbor
        query = """
        CALL db.index.vector.queryNodes('hsn_vector_index', 1, $embedding)
        YIELD node, score
        WHERE score > $threshold
        RETURN node.code as hsn_code
        """
        
        with driver.session() as session:
            result = session.run(query, embedding=embedding, threshold=threshold).single()
            if result:
                return result["hsn_code"]
    except Exception as e:
        # Fails silently to allow fallback to OCR
        # logger.error(f"HSN Vector Search Error: {e}")
        pass
        
    return None

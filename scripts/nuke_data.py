import os
import sys
import logging
from dotenv import load_dotenv

# Path setup
sys.path.append(os.getcwd())

from src.services.database import connect_db, get_db_driver, close_db
from src.services.storage import init_storage_client, get_storage_client
from src.core.config import R2_BUCKET_NAME as BUCKET_NAME

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NukeData")

def nuke_neo4j():
    driver = get_db_driver()
    if not driver:
        connect_db()
        driver = get_db_driver()
    
    if not driver:
        logger.error("Could not connect to Neo4j.")
        return

    logger.info("Cleaning Neo4j Database...")
    # Delete Invoices, Line Items, Global Products?, Suppliers?
    # User said "all invoice data".
    # We will keep Users and potentially configured Suppliers if they are master data?
    # But often "start again" means clear transaction history.
    
    queries = [
        "MATCH (i:Invoice) DETACH DELETE i",
        "MATCH (l:Line_Item) DETACH DELETE l",
        "MATCH (e:InvoiceExample) DETACH DELETE e", # User said "start again", maybe clear examples too to re-mine?
        # "MATCH (s:Supplier) DETACH DELETE s", # Maybe too aggressive? Let's ask or just keep suppliers.
    ]
    
    # We will delete Invoices and Examples. We will keep Suppliers for now unless they are auto-created garbage.
    # Actually, Suppliers are often improved over time. If we want a clean slate, maybe delete them too.
    # Let's delete Invoices and LineItems.
    
    with driver.session() as session:
        # Delete Invoices & Line Items
        res = session.run("MATCH (i:Invoice) DETACH DELETE i RETURN count(i) as cnt")
        logger.info(f"Deleted {res.single()['cnt']} Invoices")
        
        res = session.run("MATCH (l:Line_Item) DETACH DELETE l RETURN count(l) as cnt")
        logger.info(f"Deleted {res.single()['cnt']} Line Items")
        
        # Delete Processing/Draft
        # res = session.run("MATCH (n) WHERE n.status IN ['PROCESSING', 'DRAFT'] DETACH DELETE n RETURN count(n) as cnt")
        # Covered by Invoice delete if they are label Invoice
        
        # Delete Invoice Examples (Gold standards) - User said "start again"
        res = session.run("MATCH (e:InvoiceExample) DETACH DELETE e RETURN count(e) as cnt")
        logger.info(f"Deleted {res.single()['cnt']} Invoice Examples")

def nuke_r2():
    # Ensure init
    init_storage_client()
    s3_client = get_storage_client()
        
    if not s3_client:
        logger.warning("S3 Client not available. Skipping R2 cleaning.")
        return

    logger.info(f"Cleaning R2 Bucket: {BUCKET_NAME}...")
    
    try:
        # List all objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=BUCKET_NAME)
        
        objects_to_delete = []
        count = 0
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # Optional: Filter by prefix if we only want to delete 'invoices/'
                    # if obj['Key'].startswith('invoices/'):
                    objects_to_delete.append({'Key': obj['Key']})
                    count += 1
        
        if objects_to_delete:
            # Delete in batches of 1000
            for i in range(0, len(objects_to_delete), 1000):
                batch = objects_to_delete[i:i+1000]
                s3_client.delete_objects(Bucket=BUCKET_NAME, Delete={
                    'Objects': batch
                })
            logger.info(f"Deleted {count} files from R2.")
        else:
            logger.info("Bucket is already empty.")

    except Exception as e:
        logger.error(f"R2 Cleanup failed: {e}")

if __name__ == "__main__":
    load_dotenv()
    response = input("This will DELETE ALL INVOICE DATA from Neo4j and R2. Are you sure? (y/n): ")
    if response.lower() == 'y':
        nuke_neo4j()
        nuke_r2()
        logger.info("Nuke complete. System is clean.")
    else:
        logger.info("Operation cancelled.")

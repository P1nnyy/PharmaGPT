
import os
import sys
from dotenv import load_dotenv
from neo4j import GraphDatabase
import boto3

# Load environment variables
load_dotenv()

def check_neo4j():
    print("\n--- Checking Neo4j ---")
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("✅ Neo4j: CONNECTED")
        
        # Check Vector Index
        with driver.session() as session:
            # Check for invoice_examples_index
            result = session.run("SHOW INDEXES YIELD name, state, type WHERE name = 'invoice_examples_index'").single()
            if result:
                print(f"✅ Vector Index 'invoice_examples_index': FOUND (State: {result['state']})")
            else:
                print("❌ Vector Index 'invoice_examples_index': NOT FOUND")
                
            # Check for hsn_vector_index (Added recently)
            result_hsn = session.run("SHOW INDEXES YIELD name, state, type WHERE name = 'hsn_vector_index'").single()
            if result_hsn:
                print(f"✅ Vector Index 'hsn_vector_index': FOUND (State: {result_hsn['state']})")
            else:
                print("⚠️  Vector Index 'hsn_vector_index': NOT FOUND (Might need server restart to init)")
                
    except Exception as e:
        print(f"❌ Neo4j Error: {e}")
    finally:
        if driver:
            driver.close()

def check_r2():
    print("\n--- Checking R2 Storage ---")
    endpoint = os.getenv("R2_ENDPOINT_URL")
    key_id = os.getenv("AWS_ACCESS_KEY_ID")
    secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket = os.getenv("R2_BUCKET_NAME")
    
    if not (endpoint and key_id and secret and bucket):
        print("⚠️  R2 Configuration Missing in .env")
        return

    try:
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret
        )
        
        # List 1 object to prove access
        response = s3.list_objects_v2(Bucket=bucket, MaxKeys=1)
        
        if 'Contents' in response:
            count = len(response['Contents'])
            print(f"✅ R2: CONNECTED (Found {count} objects)")
        else:
            print("✅ R2: CONNECTED (Bucket is empty)")
            
    except Exception as e:
        print(f"❌ R2 Error: {e}")

if __name__ == "__main__":
    print("Starting System Health Check...")
    check_neo4j()
    check_r2()
    print("\nHealth Check Complete.")

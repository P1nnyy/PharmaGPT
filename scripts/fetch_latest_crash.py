import os
import json
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

def fetch_latest_crash():
    load_dotenv()
    
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not public_key or not secret_key:
        print(json.dumps({"error": "Missing Langfuse credentials in environment variables."}))
        return

    # Langfuse API endpoints
    # Traces: /api/public/traces
    # Observations: /api/public/observations
    
    try:
        auth = HTTPBasicAuth(public_key, secret_key)
        
        # 1. Fetch latest traces
        # We look for the most recent trace in the project
        params = {
            "limit": 5,
            "orderBy": "timestamp.desc"
        }
        
        response = requests.get(f"{host}/api/public/traces", auth=auth, params=params)
        response.raise_for_status()
        traces = response.json().get("data", [])
        
        if not traces:
            print(json.dumps({"error": "No traces found in Langfuse."}))
            return

        # 2. Find the most recent one with an error or just the latest one
        # For now, we take the latest trace
        target_trace = traces[0]
        trace_id = target_trace["id"]
        
        # 3. Fetch observations for this trace to get node-level details
        obs_params = {
            "traceId": trace_id
        }
        obs_response = requests.get(f"{host}/api/public/observations", auth=auth, params=obs_params)
        obs_response.raise_for_status()
        observations = obs_response.json().get("data", [])
        
        # 4. Construct Debug Info
        debug_info = {
            "trace_id": trace_id,
            "timestamp": target_trace.get("timestamp"),
            "input": target_trace.get("input"),
            "output": target_trace.get("output"),
            "nodes": []
        }
        
        for obs in observations:
            node_info = {
                "name": obs.get("name"),
                "type": obs.get("type"),
                "level": obs.get("level"),
                "status_message": obs.get("statusMessage"),
                "input": obs.get("input"),
                "output": obs.get("output")
            }
            debug_info["nodes"].append(node_info)
                
        # 5. Output JSON
        print(json.dumps(debug_info, indent=2))
        
    except Exception as e:
        print(json.dumps({"error": f"Failed to fetch from Langfuse API: {str(e)}"}))

if __name__ == "__main__":
    fetch_latest_crash()

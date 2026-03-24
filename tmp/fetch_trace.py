from langfuse import Langfuse
import json
import os

def fetch_trace_data(trace_id):
    langfuse = Langfuse(
        public_key="pk-lf-00a678e0-7fec-4155-a84c-9159c13fc333",
        secret_key="sk-lf-a18ed72e-731e-4244-8cee-327de0ecf702",
        host="https://cloud.langfuse.com"
    )
    
    print(f"Fetching trace: {trace_id}")
    try:
        trace = langfuse.get_trace(trace_id)
        # print(json.dumps(trace.dict(), indent=2, default=str))
        
        # Get observations (spans, generations)
        observations = langfuse.get_observations(trace_id=trace_id)
        
        print("\nObservations:")
        for obs in observations.data:
            print(f"- Type: {obs.type}, Name: {obs.name}, Status: {obs.level}")
            if obs.type == "generation":
                print(f"  Input: {obs.input[:100]}...")
                print(f"  Output: {obs.output[:500]}...")
            if obs.level == "ERROR":
                print(f"  Error: {obs.status_message}")
                
    except Exception as e:
        print(f"Error fetching trace: {e}")

if __name__ == "__main__":
    fetch_trace_data("2b20941ac3cf4ab3db1d6cff771cbd82")

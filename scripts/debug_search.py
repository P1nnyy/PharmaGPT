import requests
import json
from fuzzywuzzy import fuzz

def debug_search(product_name):
    print(f"Searching for: {product_name}")
    search_url = "https://www.1mg.com/api/v1/search/autocomplete"
    params = {"name": product_name, "pageSize": 10}
    
    try:
        response = requests.get(search_url, params=params, timeout=10)
        data = response.json()
        
        items = []
        if isinstance(data, list): items = data
        elif isinstance(data, dict):
            if 'results' in data: items = data['results']
            elif 'suggestions' in data: items = data['suggestions']
            elif 'result' in data: items = data['result']
            
        print(f"Found {len(items)} raw items.")
        
        for item in items:
            name = item.get('name', 'Unknown')
            url = item.get('url_path', '')
            score = fuzz.token_set_ratio(product_name.lower(), name.lower())
            print(f"- [{score}% match] {name} ({url})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_search("ONDERO MET 2.5/1000 M")

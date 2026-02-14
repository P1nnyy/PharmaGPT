import requests
import json

def test_search(query):
    print(f"--- Searching: '{query}' ---")
    url = "https://www.1mg.com/api/v1/search/autocomplete"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Origin': 'https://www.1mg.com',
        'Referer': 'https://www.1mg.com/'
    }
    params = {"name": query, "pageSize": 5}
    try:
        r = requests.get(url, params=params, headers=headers)
        data = r.json()
        
        items = []
        if isinstance(data, list): items = data
        elif isinstance(data, dict):
             if 'results' in data: items = data['results']
             elif 'suggestions' in data: items = data['suggestions']
             elif 'result' in data: items = data['result']
             
        for item in items:
            print(f"  Result: {item.get('name')} | Link: {item.get('url_path')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search("LIVO-LUK")
    test_search("LIVO LUK")
    test_search("LIVO")

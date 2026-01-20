import requests
import sys

def ping():
    try:
        print("Pinging http://localhost:5001/ ...")
        # Assuming root or health endpoint exists. If not, try /auth/me with dummy token or just check connection.
        # We'll try to just connect.
        try:
            r = requests.get("http://localhost:5001/", timeout=5)
            print(f"Root status: {r.status_code}")
        except Exception as e:
            print(f"Root ping failed: {e}")

        print("Pinging http://localhost:5001/products/all ... (Timeout 5s)")
        r = requests.get("http://localhost:5001/products/all", timeout=5)
        print(f"Products status: {r.status_code}")
        return True
    except Exception as e:
        print(f"Server Unreachable: {e}")
        return False

if __name__ == "__main__":
    ping()

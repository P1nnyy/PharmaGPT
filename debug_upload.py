import requests

url = "http://localhost:8000/api/upload"
file_path = "/Users/pranavgupta/.gemini/antigravity/brain/37b9e61a-40a4-4a09-9ac6-4427ffec2ba1/uploaded_image_1764482018368.png"

try:
    with open(file_path, "rb") as f:
        files = {"file": f}
        response = requests.post(url, files=files)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        with open("upload_response.json", "w") as f:
            f.write(response.text)
except Exception as e:
    print(f"Error: {e}")

import urllib.request

try:
    resp = urllib.request.urlopen('http://127.0.0.1:5173/')
    print("5173 OK:", resp.read()[:50])
except Exception as e:
    print("5173 Error:", e)

try:
    resp = urllib.request.urlopen('http://127.0.0.1:5001/')
    print("5001 OK:", resp.read()[:50])
except Exception as e:
    headers = e.headers
    print("5001 Error:", e, e.read()[:50])

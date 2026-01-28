#!/usr/bin/env python3
"""Simple smoke tests for the Techfy Demand API endpoints.

Run from the `backend` folder with the venv activated:
  .venv\Scripts\activate
  python scripts/smoke_test.py

If you want nicer output and have `requests` installed, the script will use it; otherwise it falls back to urllib.
"""
import json

def _use_requests():
    try:
        import requests
        return requests
    except Exception:
        return None

reqs = _use_requests()

def get(url):
    if reqs:
        r = reqs.get(url, timeout=10)
        return r.status_code, r.text
    else:
        from urllib.request import urlopen, Request
        req = Request(url, headers={"User-Agent": "smoke-test"})
        with urlopen(req, timeout=10) as r:
            return r.getcode(), r.read().decode('utf-8')

def pretty_print(name, status, text):
    print(f"=== {name} (status {status}) ===")
    try:
        obj = json.loads(text)
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception:
        print(text[:2000])
    print()

def main():
    base = "http://localhost:8000"
    endpoints = [
        ("historic", f"{base}/api/historic?sku=GS-019"),
        ("forecast", f"{base}/api/forecast?sku=GS-019&horizon=7"),
        ("social", f"{base}/api/social?top_n=5"),
    ]

    for name, url in endpoints:
        try:
            status, text = get(url)
            pretty_print(name, status, text)
        except Exception as e:
            print(f"Error calling {url}: {e}\n")

if __name__ == '__main__':
    main()

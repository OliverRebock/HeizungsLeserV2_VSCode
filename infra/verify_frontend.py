import httpx
import sys

def check_frontend():
    print("Checking Frontend on Port 3001...")
    try:
        # Re-check httpx usage
        with httpx.Client() as client:
            resp = client.get("http://localhost:3001/")
            print(f"Status: {resp.status_code}")
            # Header check
            print(f"Cache-Control Header: {resp.headers.get('Cache-Control')}")
            if "v2.0.4-live-check" in resp.text:
                print("SUCCESS: Version v2.0.4-live-check found in response!")
            else:
                print("FAILURE: Version string not found.")
                # Print first 500 chars to debug
                print("Response Preview:")
                print(resp.text[:500])
    except Exception as e:
        print(f"Error connecting to frontend: {e}")

if __name__ == "__main__":
    check_frontend()

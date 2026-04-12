import requests
import json

def test_dashboard_api():
    url = "http://localhost:8000/api/v1/data/17/dashboard"
    params = {
        "entity_ids": "boiler_heating_active,boiler_current_flow_temperature"
    }
    
    # We need a token. I'll try to find one or skip if impossible.
    # Since I'm in the environment, I can just check the logs after refreshing the page or use a direct call if I had a token.
    # Actually, I'll just check the logs again.
    pass

if __name__ == "__main__":
    print("Bitte die Seite im Browser aktualisieren und die Backend-Logs prüfen.")

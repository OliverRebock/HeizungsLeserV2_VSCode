import os

from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

def check_binary_data():
    url = os.getenv('INFLUX_URL', 'http://10.8.0.1:8086')
    token = os.getenv('INFLUX_TOKEN')
    org = os.getenv('INFLUX_ORG', 'heizungsleser')
    bucket = os.getenv('INFLUX_BUCKET', 'ha_Input_rebock')

    if not token:
        raise RuntimeError('INFLUX_TOKEN is required')
    
    # Wir suchen nach der Heizungs-Aktivität (vermutlich binary)
    # Ich suche erst mal alle binary entities
    print(f"Connecting to {url} (Bucket: {bucket})...")
    with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
        query = f'''
        from(bucket: "{bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_field"] == "value")
        |> group(columns: ["entity_id"])
        |> last()
        '''
        try:
            tables = client.query_api().query(query)
            print("Letzte Werte für alle Entities:")
            for table in tables:
                for record in table.records:
                    eid = record.values.get("entity_id")
                    val = record.get_value()
                    # Wir suchen speziell nach "heizen" oder "active"
                    if "heizen" in str(eid).lower() or "active" in str(eid).lower() or "heating" in str(eid).lower():
                        print(f"FOUND: {eid} -> {val} ({record.get_time()})")
        except Exception as e:
            print(f"Fehler: {e}")

if __name__ == '__main__':
    check_binary_data()

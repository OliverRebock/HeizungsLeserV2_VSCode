from influxdb_client import InfluxDBClient
from datetime import datetime, timezone

def analyze_points():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_rebock'
    
    print(f"Connecting to {url} (Bucket: {bucket})...")
    with InfluxDBClient(url=url, token=token, org=org, timeout=10000) as client:
        entities = ["boiler_compressor_current_power", "boiler_compressor_power_output"]
        
        # Heutiges Datum ab 17:00 Uhr UTC
        # Aktuelle UTC-Zeit: ca. 18:57 (20:57 Lokalzeit)
        # Wir fragen die letzten 8 Stunden ab, um 17:00 bis jetzt abzudecken
        for entity in entities:
            print(f"\n--- Analyse fÃ¼r {entity} ---")
            query = f'''
            from(bucket: "{bucket}")
            |> range(start: -8h)
            |> filter(fn: (r) => r["entity_id"] == "{entity}")
            |> filter(fn: (r) => r["_field"] == "value")
            '''
            try:
                tables = client.query_api().query(query)
                if not tables:
                    print(f"Keine Daten fÃ¼r '{entity}' in den letzten 8h gefunden.")
                    continue
                
                points = []
                for table in tables:
                    for record in table.records:
                        points.append((record.get_time(), record.get_value()))
                
                # Sortieren nach Zeit
                points.sort(key=lambda x: x[0])
                
                print(f"Gefundene Punkte: {len(points)}")
                if len(points) > 10:
                    print("... (Anzeige auf letzte 10 Punkte beschrÃ¤nkt)")
                    for p in points[-10:]:
                        print(f"  {p[0]} -> {p[1]}")
                else:
                    for p in points:
                        print(f"  {p[0]} -> {p[1]}")
                        
            except Exception as e:
                print(f"Fehler bei der Abfrage von {entity}: {e}")

if __name__ == '__main__':
    analyze_points()

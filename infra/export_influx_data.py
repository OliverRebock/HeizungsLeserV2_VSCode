from influxdb_client import InfluxDBClient
import csv
import os
from datetime import datetime

def export_influx_to_csv():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_rebock'
    
    export_path = r'C:\temp\influx_export_rebock.csv'
    
    print(f"Verbinde zu {url} (Bucket: {bucket})...")
    
    try:
        with InfluxDBClient(url=url, token=token, org=org, timeout=300000) as client:
            # Wir fragen ALLES ab (range start: 0)
            # Da das Bucket sehr groß sein kann, streamen wir die Daten
            query = f'''
            from(bucket: "{bucket}")
            |> range(start: 0)
            '''
            
            print("Starte Datenabfrage (dies kann bei großen Datenmengen dauern)...")
            query_api = client.query_api()
            
            # Wir schreiben direkt in die CSV-Datei
            with open(export_path, mode='w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                # Header
                writer.writerow(['time', 'measurement', 'field', 'value', 'entity_id', 'domain', 'friendly_name'])
                
                count = 0
                tables = query_api.query(query)
                for table in tables:
                    for record in table.records:
                        writer.writerow([
                            record.get_time(),
                            record.get_measurement(),
                            record.get_field(),
                            record.get_value(),
                            record.values.get('entity_id', ''),
                            record.values.get('domain', ''),
                            record.values.get('friendly_name', '')
                        ])
                        count += 1
                        if count % 10000 == 0:
                            print(f"{count} Datensätze exportiert...")
            
            print(f"Export erfolgreich abgeschlossen. {count} Datensätze in {export_path} gespeichert.")

    except Exception as e:
        print(f"Fehler beim Export: {e}")

if __name__ == '__main__':
    export_influx_to_csv()

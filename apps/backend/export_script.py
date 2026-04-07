from influxdb_client import InfluxDBClient
import sys

def export_bucket():
    url = "http://10.8.0.1:8086"
    token = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
    org = "heizungsleser"
    bucket = "ha_Input_beyer1V2"
    
    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()
    
    # Abfrage der letzten 24 Stunden
    query = f'from(bucket: "{bucket}") |> range(start: -24h)'
    
    try:
        csv_result = query_api.query_csv(query)
        for line in csv_result:
            print(line)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    finally:
        client.close()

if __name__ == "__main__":
    export_bucket()

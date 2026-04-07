from influxdb_client import InfluxDBClient, BucketRetentionRules
import time

def recreate_bucket():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org_name = 'heizungsleser'
    bucket_name = 'ha_Input_beyer1V2'
    retention_seconds = 7776000 # 90 Tage (aus vorheriger Abfrage)

    client = InfluxDBClient(url=url, token=token, org=org_name)
    buckets_api = client.buckets_api()
    organizations_api = client.organizations_api()

    try:
        # 1. Org ID finden
        orgs = organizations_api.find_organizations(org=org_name)
        if not orgs:
            print(f"Fehler: Organisation '{org_name}' nicht gefunden.")
            return
        org_id = orgs[0].id

        # 2. Bestehendes Bucket finden
        bucket = buckets_api.find_bucket_by_name(bucket_name)
        if bucket:
            print(f"Lösche Bucket '{bucket_name}' (ID: {bucket.id})...")
            buckets_api.delete_bucket(bucket)
            print("Bucket erfolgreich gelöscht. Warte kurz...")
            time.sleep(2) # Kurze Pause für InfluxDB
        else:
            print(f"Bucket '{bucket_name}' existiert nicht. Erstelle neu...")

        # 3. Bucket neu erstellen (Index wird zurückgesetzt)
        retention_rule = BucketRetentionRules(type="expire", every_seconds=retention_seconds)
        new_bucket = buckets_api.create_bucket(bucket_name=bucket_name, retention_rules=[retention_rule], org_id=org_id)
        
        print(f"Bucket '{bucket_name}' wurde erfolgreich mit ID {new_bucket.id} neu erstellt.")
        print("Alle historischen Index-Leichen wurden damit vollständig entfernt.")

    except Exception as e:
        print(f"Fehler beim Neuerstellen des Buckets: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    recreate_bucket()

from influxdb_client import InfluxDBClient
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules

URL = "http://10.8.0.1:8086"
TOKEN = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
ORG = "heizungsleser"
BUCKET_NAME = "ha_Input_rebock"

client = InfluxDBClient(url=URL, token=TOKEN, org=ORG)
buckets_api = client.buckets_api()

bucket = buckets_api.find_bucket_by_name(BUCKET_NAME)

if bucket:
    print(f"Lösche Bucket: {BUCKET_NAME} (ID: {bucket.id})")
    buckets_api.delete_bucket(bucket)
    print("Bucket erfolgreich gelöscht.")
else:
    print(f"Bucket {BUCKET_NAME} nicht gefunden, erstelle neu...")

retention_rules = BucketRetentionRules(type="expire", every_seconds=7776000)
new_bucket = buckets_api.create_bucket(bucket_name=BUCKET_NAME, org=ORG, retention_rules=retention_rules)

print(f"Bucket {BUCKET_NAME} neu erstellt mit ID: {new_bucket.id}")
print(f"Retention eingestellt auf: {7776000} Sekunden (90 Tage)")

client.close()

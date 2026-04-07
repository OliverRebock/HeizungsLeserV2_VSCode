import asyncio
from influxdb_client import InfluxDBClient
from influxdb_client.domain.permission import Permission
from influxdb_client.domain.permission_resource import PermissionResource
from influxdb_client.domain.authorization import Authorization

async def test_provisioning():
    url = "http://10.8.0.1:8086"
    token = "-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=="
    org_name = "heizungsleser"
    test_bucket_name = "junie_test_bucket"

    print(f"Connecting to {url}...")
    client = InfluxDBClient(url=url, token=token, org=org_name)
    
    try:
        # 1. Org ID finden
        print(f"Finding Org ID for '{org_name}'...")
        orgs = client.organizations_api().find_organizations(org=org_name)
        if not orgs:
            print(f"FAILED: Organization '{org_name}' not found!")
            return
        org_id = orgs[0].id
        print(f"SUCCESS: Org ID is {org_id}")

        # 2. Bucket erstellen
        print(f"Creating bucket '{test_bucket_name}'...")
        buckets_api = client.buckets_api()
        existing = buckets_api.find_bucket_by_name(test_bucket_name)
        if existing:
            print(f"Bucket already exists (ID: {existing.id}), deleting first...")
            buckets_api.delete_bucket(existing.id)
        
        bucket = buckets_api.create_bucket(bucket_name=test_bucket_name, org_id=org_id)
        print(f"SUCCESS: Bucket created with ID {bucket.id}")

        # 3. Token generieren
        print(f"Generating token for bucket {test_bucket_name}...")
        read_perm = Permission(action="read", resource=PermissionResource(type="buckets", id=bucket.id, org_id=org_id))
        write_perm = Permission(action="write", resource=PermissionResource(type="buckets", id=bucket.id, org_id=org_id))
        
        auth = Authorization(
            org_id=org_id,
            description=f"Test Token for {test_bucket_name}",
            permissions=[read_perm, write_perm]
        )
        
        created_auth = client.authorizations_api().create_authorization(authorization=auth)
        print(f"SUCCESS: Token generated: {created_auth.token}")

        # 4. Cleanup
        print(f"Cleanup: Deleting test bucket...")
        # buckets_api.delete_bucket(bucket.id)
        # print("Cleanup done.")

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_provisioning())

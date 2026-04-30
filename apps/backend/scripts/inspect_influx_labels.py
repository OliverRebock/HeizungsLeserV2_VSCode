import argparse
import asyncio
import json
import re

from influxdb_client import InfluxDBClient
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Influx metadata label fields")
    parser.add_argument("--device-id", type=int, default=17)
    parser.add_argument("--bucket", type=str, default=None)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--limit", type=int, default=25)
    return parser.parse_args()


async def get_bucket_for_device(device_id: int) -> str | None:
    async with SessionLocal() as db:
        result = await db.execute(
            text("SELECT influx_database_name FROM device WHERE id = :device_id") ,
            {"device_id": device_id},
        )
        return result.scalar_one_or_none()


def query_field_keys(client: InfluxDBClient, bucket: str) -> list[str]:
    query_api = client.query_api()
    query = f'''
import "influxdata/influxdb/schema"
schema.fieldKeys(bucket: "{bucket}")
'''
    return sorted(
        {
            record.get_value()
            for table in query_api.query(query=query)
            for record in table.records
            if record.get_value()
        }
    )


def query_last_values(
    client: InfluxDBClient,
    bucket: str,
    field: str,
    days: int,
    limit: int,
) -> list[dict[str, str | None]]:
    query_api = client.query_api()
    query = f'''
from(bucket: "{bucket}")
|> range(start: -{days}d)
|> filter(fn: (r) => r["_field"] == "{field}")
|> keep(columns: ["_time", "_measurement", "entity_id", "_field", "_value"])
|> group(columns: ["entity_id", "_field"])
|> last()
|> sort(columns: ["entity_id"])
'''
    rows: list[dict[str, str | None]] = []
    for table in query_api.query(query=query):
        for record in table.records:
            rows.append(
                {
                    "entity_id": record.values.get("entity_id"),
                    "measurement": record.get_measurement(),
                    "value": None if record.get_value() is None else str(record.get_value()),
                    "time": record.get_time().isoformat() if record.get_time() else None,
                }
            )
    return rows[:limit]


async def main() -> None:
    args = parse_args()
    bucket = args.bucket or await get_bucket_for_device(args.device_id)
    if not bucket:
        raise SystemExit(f"No bucket found for device_id={args.device_id}")

    client = InfluxDBClient(
        url=settings.INFLUXDB_URL,
        token=settings.INFLUXDB_TOKEN,
        org=settings.INFLUXDB_ORG,
    )
    try:
        field_names = query_field_keys(client, bucket)
        interesting_fields = [
            field
            for field in field_names
            if re.search(r"(name|friendly|desc|label|title)", field, re.IGNORECASE)
        ]

        print(f"BUCKET={bucket}")
        print("INTERESTING_FIELDS=" + json.dumps(interesting_fields, ensure_ascii=False))

        for field in interesting_fields:
            rows = query_last_values(client, bucket, field, args.days, args.limit)
            print(f"FIELD={field}")
            print(json.dumps(rows, ensure_ascii=False))
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
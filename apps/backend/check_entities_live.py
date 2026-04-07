from influxdb_client import InfluxDBClient

def check_specific_entities():
    url = 'http://10.8.0.1:8086'
    token = '-hBacWyE-7_nWSH2N4-UjV2p2yXbst7B00ir3TjJagiGMR7bpqR4HYuY1R6a8mOcifKgdtIH47uK9zCoqUHG2Q=='
    org = 'heizungsleser'
    bucket = 'ha_Input_beyer1V2'
    
    # Die vom User genannten Entitäten (IDs müssen wir ggf. erraten/mappen)
    targets = [
        'boiler_air_inlet_temperature_tl2',
        'boiler_aux_heater',
        'boiler_aux_heater_status',
        'boiler_burner_current_power',
        'boiler_circulation_pump_speed',
        'boiler_compressor_activity'
    ]

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    print(f"Prüfe Live-Status (letzte 2h) im Bucket '{bucket}':")
    
    for eid in targets:
        query = f'''
        from(bucket: "{bucket}")
          |> range(start: -2h)
          |> filter(fn: (r) => r["entity_id"] == "{eid}")
          |> last()
        '''
        try:
            tables = query_api.query(query)
            if tables:
                for table in tables:
                    for record in table.records:
                        print(f"✅ {eid}: {record.get_value()} (Zeit: {record.get_time()})")
            else:
                print(f"❌ {eid}: KEINE DATEN in den letzten 2h")
        except Exception as e:
            print(f"⚠️ {eid}: Fehler bei Abfrage: {e}")

    # Auch mal schauen, was ÜBERHAUPT da ist (Auszug)
    print("\nÜbersicht aller aktuell sendenden Entitäten (Top 10):")
    query_all = f'''
    from(bucket: "{bucket}")
      |> range(start: -1h)
      |> keep(columns: ["entity_id"])
      |> group(columns: ["entity_id"])
      |> distinct(column: "entity_id")
      |> limit(n: 10)
    '''
    try:
        tables = query_api.query(query_all)
        for table in tables:
            for record in table:
                print(f"- {record.get_value()}")
    except:
        pass

    client.close()

if __name__ == "__main__":
    check_specific_entities()

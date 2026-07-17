import openviking as ov

client = ov.SyncHTTPClient(url="http://localhost:1933",api_key='kk123123')

try:
    client.initialize()

    results = client.find("test_ipmi_aggregate_in_band")
    for r in results.resources:
        print(f"  {r.uri} (score: {r.score:.4f})")

finally:
    client.close()
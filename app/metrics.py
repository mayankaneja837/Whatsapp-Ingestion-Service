http_requests_total = {}

webhook_requests_total = {}

latency_buckets = {
    100: 0,
    500: 0,
    float("inf"): 0
}

latency_count = 0

def inc_http_requests(path:str,status:int):
    key = (path,str(status))
    http_requests_total[key] = http_requests_total.get(key,0) + 1

def inc_webhook_result(result:str):
    webhook_requests_total[result] = webhook_requests_total.get(result,0) +1

def observe_latency(ms:float):
    global latency_count
    latency_count += 1

    for bucket in latency_buckets:
        if ms <= bucket:
            latency_buckets[bucket] += 1
            break

def render_prometheus() -> str:
    lines = []

    for (path,status), count in http_requests_total.items():
        lines.append(f'http_requests_total{{path="{path}",status="{status}"}} {count}')

    for result,count in webhook_requests_total.items():
        lines.append(f'webhook_requests_total{{result="{result}"}} {count}')

    for bucket,count in latency_buckets.items():
        bucket_label = "+Inf" if bucket == float("inf") else str(int(bucket))
        lines.append(f'request_latency_ms_bucket{{le="{bucket_label}"}} {count}') 

        lines.append(f"request_latency_ms_count {latency_count}")

    
    return "\n".join(lines) + "\n"

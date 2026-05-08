import json
from datetime import datetime

from prometheus_api_client import PrometheusConnect


PROM_URL = "http://10.17.151.170:9090"
ALIVE_THRESHOLD = 60

prom = PrometheusConnect(url=PROM_URL, disable_ssl=True)


def get_node_metrics_json():
    alive_filter = f'and on(instance) (time() - push_time_seconds < {ALIVE_THRESHOLD})'

    metric_queries = {
        "cpu_usage_percent": (
            'clamp_max(avg by (instance) '
            '(rate(node_cpu_seconds_total{mode!~"idle|iowait"}[5m])) * 100, 100) '
            f'{alive_filter}'
        ),
        "memory_usage_percent": (
            '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 '
            f'{alive_filter}'
        ),
        "network_throughput_mbps": (
            'sum by (instance) ('
            'rate(node_network_receive_bytes_total{device!~"lo|docker.*|veth.*"}[5m]) + '
            'rate(node_network_transmit_bytes_total{device!~"lo|docker.*|veth.*"}[5m])'
            ') / 1024 / 1024 '
            f'{alive_filter}'
        ),
        "disk_io_mbps": (
            'sum by (instance) ('
            'rate(node_disk_read_bytes_total{device!~"loop.*|ram.*"}[5m]) + '
            'rate(node_disk_written_bytes_total{device!~"loop.*|ram.*"}[5m])'
            ') / 1024 / 1024 '
            f'{alive_filter}'
        ),
    }

    hardware_value_queries = {
        "cpu_sockets": f'node_hardware_cpu_sockets{{job="node"}} {alive_filter}',
        "memory_modules_count": f'node_hardware_memory_modules{{job="node"}} {alive_filter}',
        "memory_total_bytes": f'node_hardware_memory_total_bytes{{job="node"}} {alive_filter}',
        "disk_devices_count": f'node_hardware_disk_devices{{job="node"}} {alive_filter}',
        "disk_total_bytes": f'node_hardware_disk_total_bytes{{job="node"}} {alive_filter}',
    }

    hardware_value_map = {
        "cpu_sockets": ("cpu", "count"),
        "memory_modules_count": ("memory", "count"),
        "memory_total_bytes": ("memory", "value"),
        "disk_devices_count": ("disk", "count"),
        "disk_total_bytes": ("disk", "value"),
    }

    hardware_info_queries = {
        "cpu": f'node_hardware_cpu_info{{job="node"}} {alive_filter}',
        "memory": f'node_hardware_memory_info{{job="node"}} {alive_filter}',
        "disk": f'node_hardware_disk_info{{job="node"}} {alive_filter}',
    }

    metrics_data = {}

    def ensure_instance(instance):
        return metrics_data.setdefault(instance, {
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "metrics": {},
            "hardware": {
                "cpu": [],
                "memory": [],
                "disk": [],
            },
            "_hardware_summary": {
                "cpu": {},
                "memory": {},
                "disk": {},
            },
        })

    def query_items(name, promql):
        try:
            return prom.custom_query(query=promql)
        except Exception as e:
            print(f"Query error for {name}: {e}")
            return []

    def safe_int(value):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def hardware_item(name="", count=None, vendor="", type_="", value=None):
        return {
            "name": name,
            "count": count,
            "vendor": vendor,
            "type": type_,
            "value": value,
        }

    def add_hardware(instance, category, item):
        ensure_instance(instance)["hardware"][category].append(item)

    for metric_name, promql in metric_queries.items():
        for item in query_items(metric_name, promql):
            instance = item["metric"].get("instance", "unknown")
            value = round(float(item["value"][1]), 2)

            ensure_instance(instance)["metrics"][metric_name] = value

    for metric_name, promql in hardware_value_queries.items():
        category, field = hardware_value_map[metric_name]

        for item in query_items(metric_name, promql):
            instance = item["metric"].get("instance", "unknown")
            value = safe_int(item["value"][1])

            ensure_instance(instance)["_hardware_summary"][category][field] = value

    for hardware_type, promql in hardware_info_queries.items():
        for item in query_items(f"hardware_{hardware_type}_info", promql):
            labels = item.get("metric", {})
            instance = labels.get("instance", "unknown")
            summary = ensure_instance(instance)["_hardware_summary"]

            if hardware_type == "cpu":
                add_hardware(instance, "cpu", hardware_item(
                    name=labels.get("model", ""),
                    count=summary["cpu"].get("count"),
                    vendor=labels.get("vendor", ""),
                    type_="cpu",
                    value=labels.get("model", ""),
                ))

            elif hardware_type == "memory":
                add_hardware(instance, "memory", hardware_item(
                    name=labels.get("part_number", ""),
                    count=1,
                    vendor=labels.get("manufacturer", ""),
                    type_="memory_module",
                    value=safe_int(labels.get("size_bytes")),
                ))

            elif hardware_type == "disk":
                add_hardware(instance, "disk", hardware_item(
                    name=labels.get("name", ""),
                    count=1,
                    vendor=labels.get("vendor", ""),
                    type_="disk_device",
                    value=safe_int(labels.get("size_bytes")),
                ))

    for instance_data in metrics_data.values():
        summary = instance_data.pop("_hardware_summary", {})

        if summary.get("cpu") and not instance_data["hardware"]["cpu"]:
            instance_data["hardware"]["cpu"].append(hardware_item(
                name="cpu",
                count=summary["cpu"].get("count"),
                vendor="",
                type_="cpu",
                value=summary["cpu"].get("count"),
            ))

        if summary.get("memory") and not instance_data["hardware"]["memory"]:
            instance_data["hardware"]["memory"].append(hardware_item(
                name="memory",
                count=summary["memory"].get("count"),
                vendor="",
                type_="memory",
                value=summary["memory"].get("value"),
            ))

        if summary.get("disk") and not instance_data["hardware"]["disk"]:
            instance_data["hardware"]["disk"].append(hardware_item(
                name="disk",
                count=summary["disk"].get("count"),
                vendor="",
                type_="disk",
                value=summary["disk"].get("value"),
            ))

    return json.dumps(metrics_data, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    print(get_node_metrics_json())
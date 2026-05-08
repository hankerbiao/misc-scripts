# All Machine Info - 节点指标采集工具

从 Prometheus 获取所有在线节点的硬件和性能指标。

## 功能

- 查询节点 CPU 使用率
- 查询节点内存使用率
- 查询网络吞吐量
- 查询磁盘 I/O
- 获取硬件信息（CPU型号、内存模块、磁盘设备）

## API 配置

- Prometheus URL: `http://10.17.151.170:9090`
- 存活阈值: 60秒（超过60秒未推送数据认为不在线）

## 依赖

```bash
pip install prometheus-api-client
```

## 输出格式

```json
{
  "192.168.1.100:9100": {
    "last_update": "2026-05-08 10:30:00",
    "metrics": {
      "cpu_usage_percent": 45.5,
      "memory_usage_percent": 62.3,
      "network_throughput_mbps": 12.5,
      "disk_io_mbps": 5.2
    },
    "hardware": {
      "cpu": [...],
      "memory": [...],
      "disk": [...]
    }
  }
}
```

## 使用方法

```bash
python all_machine_info.py
```
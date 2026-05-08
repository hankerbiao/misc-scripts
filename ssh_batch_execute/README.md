# SSH Batch Execute - 批量 SSH 命令执行工具

批量 SSH 登录多台服务器并执行命令。

## 功能

- 从 JSON 文件读取主机列表
- 支持并发执行（可配置线程数）
- 输出详细执行日志
- 汇总执行结果（成功/失败统计）

## 依赖

```bash
pip install paramiko
```

## 使用方法

```bash
# 基本用法
python ssh_batch_execute.py

# 指定主机文件和命令
python ssh_batch_execute.py -H my_hosts.json -c "your command"

# 指定并发数
python ssh_batch_execute.py -t 10
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-H, --hosts` | 主机列表 JSON 文件 | `my_valid_hosts.json` |
| `-c, --command` | 要执行的命令 | curl 安装脚本 |
| `-o, --output` | 日志输出文件 | `execution.log` |
| `-t, --threads` | 并发线程数 | 5 |

## 主机配置格式

```json
{
  "hosts": [
    {"ip": "192.168.1.100", "username": "root", "password": "xxx"},
    {"ip": "192.168.1.101", "username": "admin", "password": "yyy"}
  ]
}
```
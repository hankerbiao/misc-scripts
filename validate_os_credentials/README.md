# Validate OS Credentials - SSH 凭证校验工具

校验 `os_info.txt` 中的 SSH 用户名密码是否有效。

## 功能

- 解析 os_info.txt 文件中的主机信息
- 验证 SSH 连接（端口检测 + 认证）
- 支持并发验证
- 导出有效主机列表到 JSON

## 依赖

```bash
pip install paramiko
```

## 使用方法

```bash
# 基本用法
python validate_os_credentials.py

# 指定文件路径
python validate_os_credentials.py -f os_info.txt

# 只显示有效主机
python validate_os_credentials.py --valid-only

# 只显示无效主机
python validate_os_credentials.py --invalid-only

# 指定并发数
python validate_os_credentials.py -j 20
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-f, --file` | os_info 文件路径 | `os_info.txt` |
| `-t, --timeout` | 连接超时时间(秒) | 5 |
| `-j, --jobs` | 并发数 | 10 |
| `--valid-only` | 只显示有效的 | False |
| `--invalid-only` | 只显示无效的 | False |
| `-o, --output` | 有效主机JSON文件 | `valid_hosts.json` |

## 输出

校验完成后会生成 `valid_hosts.json`，包含所有有效主机信息。
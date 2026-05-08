#!/usr/bin/env python3
"""
校验 os_info.txt 中的 SSH 用户名密码是否正确
"""

import re
import json
import socket
import concurrent.futures
from dataclasses import dataclass
from typing import Optional

try:
    import paramiko
except ImportError:
    print("请先安装 paramiko: pip install paramiko")
    exit(1)


@dataclass
class HostInfo:
    ip: str
    username: str
    password: str


def parse_os_info(filepath: str) -> list[HostInfo]:
    """解析 os_info.txt 文件"""
    hosts = []
    with open(filepath, 'r') as f:
        content = f.read()

    # 匹配每个主机的信息块
    pattern = r'"os_ip"\s*:\s*"([^"]+)".*?"os_username"\s*:\s*"([^"]+)".*?"os_password"\s*:\s*"([^"]+)"'
    matches = re.findall(pattern, content, re.DOTALL)

    for ip, username, password in matches:
        hosts.append(HostInfo(ip=ip.strip(), username=username.strip(), password=password.strip()))

    return hosts


def validate_ssh(host: HostInfo, timeout: int = 5) -> tuple[bool, Optional[str]]:
    """验证 SSH 连接"""
    try:
        # 先检查端口是否开放
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host.ip, 22))
        sock.close()

        if result != 0:
            return False, "端口 22 未开放"

        # 尝试 SSH 连接
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host.ip,
            port=22,
            username=host.username,
            password=host.password,
            timeout=timeout,
            allow_agent=False,
            look_for_keys=False
        )
        client.close()
        return True, None

    except paramiko.AuthenticationException:
        return False, "认证失败"
    except socket.timeout:
        return False, "连接超时"
    except socket.gaierror:
        return False, "DNS解析失败"
    except Exception as e:
        return False, str(e)


def validate_host(host: HostInfo) -> dict:
    """验证单个主机并返回结果"""
    success, error = validate_ssh(host)
    return {
        "ip": host.ip,
        "username": host.username,
        "password": host.password,
        "valid": success,
        "error": error
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="校验 SSH 用户名密码")
    parser.add_argument("-f", "--file", default="os_info.txt", help="os_info 文件路径")
    parser.add_argument("-t", "--timeout", type=int, default=5, help="连接超时时间(秒)")
    parser.add_argument("-j", "--jobs", type=int, default=10, help="并发数")
    parser.add_argument("--valid-only", action="store_true", help="只显示有效的")
    parser.add_argument("--invalid-only", action="store_true", help="只显示无效的")
    parser.add_argument("-o", "--output", default="valid_hosts.json", help="保存有效主机的JSON文件路径")
    args = parser.parse_args()

    hosts = parse_os_info(args.file)
    print(f"共 {len(hosts)} 个主机待验证\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {executor.submit(validate_host, host): host for host in hosts}
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    # 按 IP 排序
    results.sort(key=lambda x: x["ip"])

    valid_count = 0
    invalid_count = 0

    for r in results:
        if r["valid"]:
            valid_count += 1
            if not args.invalid_only:
                print(f"✓ {r['ip']} - {r['username']} 验证成功")
        else:
            invalid_count += 1
            if not args.valid_only:
                print(f"✗ {r['ip']} - {r['username']} 验证失败: {r['error']}")

    print(f"\n总计: {len(results)} | 成功: {valid_count} | 失败: {invalid_count}")

    # 保存有效主机到 JSON 文件
    if valid_count > 0:
        valid_hosts = [r for r in results if r["valid"]]
        output_data = {
            "total": len(valid_hosts),
            "hosts": [{"ip": h["ip"], "username": h["username"], "password": h["password"]} for h in valid_hosts]
        }
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"有效主机信息已保存到: {args.output}")


if __name__ == "__main__":
    main()
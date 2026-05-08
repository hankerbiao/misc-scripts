#!/usr/bin/env python3
"""
批量 SSH 登录服务器并执行命令
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import paramiko
except ImportError:
    print("请先安装 paramiko: pip install paramiko")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SSHExecutor:
    def __init__(self, host: str, username: str, password: str, port: int = 22):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.client: Optional[paramiko.SSHClient] = None

    def connect(self) -> bool:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10,
                banner_timeout=30,
                auth_timeout=30
            )
            return True
        except paramiko.AuthenticationException:
            logger.error(f"[{self.host}] 认证失败")
            return False
        except paramiko.SSHException as e:
            logger.error(f"[{self.host}] SSH 连接错误: {e}")
            return False
        except Exception as e:
            logger.error(f"[{self.host}] 连接失败: {e}")
            return False

    def execute(self, command: str) -> tuple[int, str, str]:
        if not self.client:
            return (-1, "", "未连接")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=300)
            exit_code = stdout.channel.recv_exit_status()
            stdout_data = stdout.read().decode('utf-8', errors='replace')
            stderr_data = stderr.read().decode('utf-8', errors='replace')
            return (exit_code, stdout_data, stderr_data)
        except Exception as e:
            return (-1, "", str(e))

    def close(self):
        if self.client:
            self.client.close()


def load_hosts(file_path: str) -> list[dict]:
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('hosts', [])


def execute_on_host(host_info: dict, command: str, log_file) -> dict:
    result = {
        'ip': host_info['ip'],
        'username': host_info['username'],
        'success': False,
        'exit_code': None,
        'stdout': '',
        'stderr': ''
    }

    executor = SSHExecutor(
        host=host_info['ip'],
        username=host_info['username'],
        password=host_info['password']
    )

    status_line = f"\n{'='*60}\n"
    status_line += f"主机: {host_info['ip']} | 用户: {host_info['username']}\n"
    status_line += f"{'='*60}\n"
    print(status_line)
    log_file.write(status_line)
    log_file.flush()

    if not executor.connect():
        msg = f"[{host_info['ip']}] 连接失败!\n"
        print(msg)
        log_file.write(msg)
        log_file.flush()
        result['stderr'] = '连接失败'
        executor.close()
        return result

    conn_msg = f"[{host_info['ip']}] 连接成功, 正在执行命令...\n"
    print(conn_msg)
    log_file.write(conn_msg)
    log_file.flush()

    exit_code, stdout, stderr = executor.execute(command)

    result['exit_code'] = exit_code
    result['stdout'] = stdout
    result['stderr'] = stderr
    result['success'] = (exit_code == 0)

    cmd_output = f"命令: {command}\n"
    cmd_output += f"退出码: {exit_code}\n"
    cmd_output += f"\n--- 标准输出 (stdout) ---\n"
    cmd_output += stdout if stdout else "(无输出)\n"
    cmd_output += f"\n--- 标准错误 (stderr) ---\n"
    cmd_output += stderr if stderr else "(无错误)\n"

    print(cmd_output)
    log_file.write(cmd_output)
    log_file.flush()

    status = "成功" if result['success'] else "失败"
    final_msg = f"[{host_info['ip']}] 执行{status}\n"
    print(final_msg)
    log_file.write(final_msg)
    log_file.flush()

    executor.close()
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description='批量 SSH 执行命令')
    parser.add_argument('-H', '--hosts', default='my_valid_hosts.json',
                        help='主机列表 JSON 文件路径')
    parser.add_argument('-c', '--command',
                        default='curl -fsSL http://10.17.151.170:8888/download/install.sh | sudo bash',
                        help='要执行的命令')
    parser.add_argument('-o', '--output', default='execution.log',
                        help='日志输出文件')
    parser.add_argument('-t', '--threads', type=int, default=5,
                        help='并发线程数 (默认: 5)')

    args = parser.parse_args()

    hosts_file = Path(args.hosts)
    if not hosts_file.exists():
        logger.error(f"主机文件不存在: {hosts_file}")
        sys.exit(1)

    hosts = load_hosts(str(hosts_file))
    if not hosts:
        logger.error("未找到主机配置")
        sys.exit(1)

    logger.info(f"加载了 {len(hosts)} 台主机")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file_path = f"execution_{timestamp}.log"

    results = []
    success_count = 0
    fail_count = 0

    with open(log_file_path, 'w', encoding='utf-8') as log_file:
        header = f"""
{'#'*60}
批量 SSH 命令执行日志
{'#'*60}
开始时间: {datetime.now().isoformat()}
主机数量: {len(hosts)}
命令: {args.command}
日志文件: {log_file_path}
{'#'*60}

"""
        log_file.write(header)
        print(header)

        for i, host in enumerate(hosts, 1):
            logger.info(f"处理主机 {i}/{len(hosts)}: {host['ip']}")
            result = execute_on_host(host, args.command, log_file)
            results.append(result)

            if result['success']:
                success_count += 1
            else:
                fail_count += 1

        summary = f"""

{'#'*60}
执行汇总
{'#'*60}
完成时间: {datetime.now().isoformat()}
总计: {len(hosts)}
成功: {success_count}
失败: {fail_count}

失败主机列表:
"""
        for r in results:
            if not r['success']:
                summary += f"  - {r['ip']} ({r['username']})\n"

        log_file.write(summary)
        print(summary)

    logger.info(f"执行完成! 日志已保存到: {log_file_path}")
    logger.info(f"成功: {success_count}, 失败: {fail_count}")

    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
ipv4_list = [
    "10.32.129.56",
    "10.32.129.156",
    "10.32.129.191",
    "10.32.129.51",
    "10.32.129.183",
    "10.31.133.98",
    "10.31.133.95",
    "10.31.133.101",
    "10.31.133.99",
    "10.31.133.96",
    "10.8.136.112",
    "10.8.136.111",
    "10.8.136.107",
    "10.8.136.110",
    "10.8.136.108",
    "10.17.151.150",
    "10.17.151.153",
    "10.17.151.112",
    "10.17.151.151",
    "10.17.151.110",
    "10.17.151.62",
    "10.17.151.59",
    "10.17.151.60",
    "10.17.151.61",
    "10.17.151.63",
    "10.17.151.79",
    "10.17.151.58",
    "10.17.151.41",
    "10.17.151.52",
    "10.17.151.37",
    "10.17.151.54",
    "10.17.151.34",
    "10.17.151.220",
    "10.17.151.171",
    "10.17.151.187",
    "10.17.151.174",
    "10.17.151.172",
    "10.17.151.170",
    "10.17.151.212",
    "10.17.151.215",
    "10.17.151.200",
]

username = 'root'
passwd = 'admin@123'

# node_exporter 安装包本地路径（需要提前下载好）
NODE_EXPORTER_TAR_PATH = '/Users/libiao/PycharmProjects/Demo/dashboard/node_exporter-1.10.2.linux-amd64.tar.gz'

# 安装配置
INSTALL_DIR = '/opt/node_exporter'
NODE_EXPORTER_PORT = 9100

import paramiko
import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Literal
from pathlib import Path


@dataclass
class InstallResult:
    """安装结果数据类"""
    ip: str
    status: Literal['success', 'failed', 'timeout']
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def ssh_connect(host: str, username: str, password: str, timeout: int = 30) -> paramiko.SSHClient | None:
    """建立SSH连接"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host,
            username=username,
            password=password,
            timeout=timeout,
            banner_timeout=timeout
        )
        return client
    except Exception as e:
        return None


def sftp_upload(client: paramiko.SSHClient, local_path: str, remote_path: str, ip: str) -> tuple[bool, str]:
    """通过SFTP上传文件到远程服务器"""
    print(f"  [{ip}] 正在上传安装包到 {remote_path}...")
    try:
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        print(f"  [{ip}] 上传完成")
        return True, "文件上传成功"
    except FileNotFoundError:
        return False, f"本地文件不存在: {local_path}"
    except Exception as e:
        return False, f"SFTP上传失败: {str(e)}"


def run_command(client: paramiko.SSHClient, cmd: str, ip: str, timeout: int = 120) -> tuple[int, str, str]:
    """执行远程命令并返回 exit_status, stdout, stderr"""
    try:
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        out = stdout.read().decode('utf-8', errors='ignore')
        err = stderr.read().decode('utf-8', errors='ignore')
        return exit_status, out, err
    except Exception as e:
        return -1, "", str(e)


def install_node_exporter(client: paramiko.SSHClient, ip: str) -> tuple[bool, str]:
    """在远程主机上安装 prometheus-node-exporter"""
    tar_filename = Path(NODE_EXPORTER_TAR_PATH).name
    remote_tar_path = f"/tmp/{tar_filename}"
    service_name = "node_exporter"

    # Step 1: 停止旧服务（如果存在）
    print(f"  [{ip}] 检查并停止旧服务...")
    run_command(client, f"systemctl stop {service_name} 2>/dev/null || true", ip, timeout=30)

    # Step 2: 创建安装目录
    print(f"  [{ip}] 创建安装目录 {INSTALL_DIR}...")
    exit_status, _, err = run_command(client, f"mkdir -p {INSTALL_DIR}", ip, timeout=30)
    if exit_status != 0 and "File exists" not in err:
        return False, f"创建目录失败: {err[:200]}"

    # Step 3: 上传安装包
    if not Path(NODE_EXPORTER_TAR_PATH).exists():
        return False, f"本地安装包不存在: {NODE_EXPORTER_TAR_PATH}"

    success, message = sftp_upload(client, NODE_EXPORTER_TAR_PATH, remote_tar_path, ip)
    if not success:
        return False, message

    # Step 4: 解压安装包
    print(f"  [{ip}] 解压安装包到 {INSTALL_DIR}...")
    exit_status, _, err = run_command(client, f"cd {INSTALL_DIR} && tar -xzf {remote_tar_path} --strip-components=1", ip, timeout=60)
    if exit_status != 0:
        return False, f"解压失败: {err[:200]}"

    # 清理临时文件
    run_command(client, f"rm -f {remote_tar_path}", ip, timeout=30)

    # Step 5: 验证文件
    print(f"  [{ip}] 验证安装文件...")
    exit_status, out, err = run_command(client, f"test -x {INSTALL_DIR}/node_exporter && echo 'OK'", ip, timeout=30)
    if exit_status != 0 or "OK" not in out:
        return False, "验证失败: node_exporter 文件不存在或不可执行"

    # Step 6: 创建 systemd service 文件
    print(f"  [{ip}] 创建 systemd service 文件...")
    service_content = f'''[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
Type=simple
ExecStart={INSTALL_DIR}/node_exporter --web.listen-address=:{NODE_EXPORTER_PORT}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
'''
    # 写入 service 文件
    service_path = f"/etc/systemd/system/{service_name}.service"
    stdin, stdout, stderr = client.exec_command(f"cat > {service_path}", timeout=30)
    stdin.write(service_content)
    stdin.flush()
    stdin.channel.shutdown_write()
    stdout.channel.recv_exit_status()

    # Step 7: 设置权限并重新加载 systemd
    print(f"  [{ip}] 设置权限并重新加载 systemd...")
    run_command(client, f"chmod 644 {service_path}", ip, timeout=30)
    run_command(client, "systemctl daemon-reload", ip, timeout=30)

    # Step 8: 启动服务并设置开机自启
    print(f"  [{ip}] 启动服务并设置开机自启...")
    exit_status, _, err = run_command(client, f"systemctl enable {service_name} && systemctl start {service_name}", ip, timeout=30)

    # Step 9: 验证服务状态
    print(f"  [{ip}] 验证服务状态...")
    exit_status, out, err = run_command(client, f"systemctl is-active {service_name}", ip, timeout=30)
    if "active" in out.lower():
        return True, f"安装并启动成功，监听端口 {NODE_EXPORTER_PORT}"
    else:
        return False, f"服务启动失败: {err[:200]}"


def save_results(results: list[InstallResult], output_file: Path) -> None:
    """保存安装结果到JSON文件"""
    data = [asdict(r) for r in results]
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_summary(results: list[InstallResult]) -> None:
    """打印安装结果汇总"""
    success_count = sum(1 for r in results if r.status == 'success')
    failed_count = sum(1 for r in results if r.status == 'failed')

    print("\n" + "=" * 60)
    print("安装结果汇总")
    print("=" * 60)
    print(f"总计: {len(results)} 台机器")
    print(f"成功: {success_count} 台")
    print(f"失败: {failed_count} 台")
    print("=" * 60)
    print("\n详细信息:")
    print("-" * 60)
    for r in results:
        status_icon = "[OK]" if r.status == 'success' else "[FAIL]"
        print(f"{status_icon} {r.ip:18} - {r.message}")
    print("-" * 60)


def main():
    results: list[InstallResult] = []
    output_dir = Path(__file__).parent
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"install_results_{timestamp}.json"

    # 检查本地安装包
    if not Path(NODE_EXPORTER_TAR_PATH).exists():
        print(f"\n[错误] 本地安装包不存在: {NODE_EXPORTER_TAR_PATH}")
        print("请先下载 node_exporter 安装包并修改 NODE_EXPORTER_TAR_PATH 路径")
        return []

    print("\n" + "=" * 60)
    print("  prometheus-node-exporter 批量安装工具")
    print("=" * 60)
    print(f"\n安装包: {NODE_EXPORTER_TAR_PATH}")
    print(f"安装目录: {INSTALL_DIR}")
    print(f"监听端口: {NODE_EXPORTER_PORT}")
    print(f"\n目标机器数量: {len(ipv4_list)}")
    print(f"用户名: {username}")
    print("-" * 60)

    for idx, ip in enumerate(ipv4_list, 1):
        print(f"\n[{idx}/{len(ipv4_list)}] ========== 正在处理 {ip} ==========")

        print(f"  [{ip}] 建立SSH连接...", end=" ")
        client = ssh_connect(ip, username, passwd)
        if client is None:
            print("失败!")
            result = InstallResult(ip=ip, status='failed', message='SSH连接失败')
            print(f"  [{ip}] [FAIL] 连接失败，跳过安装")
        else:
            print("成功")
            success, message = install_node_exporter(client, ip)
            result = InstallResult(
                ip=ip,
                status='success' if success else 'failed',
                message=message
            )
            if success:
                print(f"  [{ip}] [OK] {message}")
            else:
                print(f"  [{ip}] [FAIL] {message}")
            client.close()

        results.append(result)

    save_results(results, output_file)
    print_summary(results)

    print(f"\n结果已保存到: {output_file}")

    return results


if __name__ == "__main__":
    main()
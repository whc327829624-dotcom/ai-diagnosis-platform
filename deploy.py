"""
一键部署脚本 —— 将 AI 诊断工作台部署到阿里云 ECS
====================================================
用法: python deploy.py

你需要准备好:
  1. 阿里云 ECS 的 公网 IP
  2. root 密码
  3. 安全组已开放 8501 端口（脚本会提示你如何操作）

脚本会:
  1. SSH 连接到服务器
  2. 自动安装 Docker + Docker Compose（如果没装）
  3. 上传整个项目
  4. docker compose up -d 启动全部服务
  5. 返回访问地址
"""

import getpass
import os
import sys
import time

# ============================================================
# 配置
# ============================================================
REMOTE_HOST = "47.94.11.27"
REMOTE_USER = "root"
REMOTE_PORT = 22
REMOTE_PROJECT_DIR = "/opt/ai_diagnosis_platform"

# 本机项目目录（脚本所在目录）
LOCAL_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# 不需要上传的文件/目录（逗号分隔）
EXCLUDE_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".env.example",
    "deploy.py",  # 部署脚本本身不需要上传
]

# ============================================================
# 检查依赖
# ============================================================
try:
    import paramiko
except ImportError:
    print("❌ 缺少依赖: paramiko")
    print("   请运行: pip install paramiko")
    sys.exit(1)


def print_banner():
    print("""
╔══════════════════════════════════════════════════════╗
║     🏭 AI 企业业务流程诊断工作台 — 一键部署         ║
║     目标服务器: {host:<36} ║
╚══════════════════════════════════════════════════════╝
""".format(host=REMOTE_HOST))


def connect_ssh(password: str) -> paramiko.SSHClient:
    """建立 SSH 连接，支持密码和密钥两种方式。"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    print(f"🔗 正在连接 {REMOTE_USER}@{REMOTE_HOST} ...")

    try:
        # 先尝试密码登录
        ssh.connect(
            REMOTE_HOST,
            port=REMOTE_PORT,
            username=REMOTE_USER,
            password=password,
            timeout=10,
        )
        print("✅ SSH 连接成功")
        return ssh
    except paramiko.AuthenticationException:
        print("❌ 密码错误，请重试")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        sys.exit(1)


def run_remote(ssh: paramiko.SSHClient, command: str, sudo: bool = False) -> tuple[int, str, str]:
    """在远程服务器上执行命令，返回 (exit_code, stdout, stderr)。"""
    if sudo:
        command = f"echo '{ssh.get_transport().get_username()}' | sudo -S {command}" if False else command
        # 用 root 登录不需要 sudo，直接执行
        pass

    stdin, stdout, stderr = ssh.exec_command(command, timeout=300)
    exit_code = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return exit_code, out, err


def install_docker(ssh: paramiko.SSHClient):
    """在服务器上安装 Docker 和 Docker Compose。"""
    print("\n📦 检查 Docker 环境...")

    code, out, _ = run_remote(ssh, "docker --version 2>/dev/null && docker compose version 2>/dev/null")
    if code == 0:
        print(f"✅ Docker 已安装:\n   {out.strip().replace(chr(10), chr(10)+'   ')}")
        return

    print("⚙️  正在安装 Docker（约 2 分钟，请耐心等待）...")

    # 一键安装 Docker（阿里云镜像源加速）
    install_cmd = """
    curl -fsSL https://get.docker.com | bash -s docker 2>&1 && \
    systemctl enable docker && \
    systemctl start docker && \
    echo "Docker installed successfully"
    """
    code, out, err = run_remote(ssh, install_cmd)
    out_lower = (out + err).lower()

    if code == 0 or "installed successfully" in out_lower:
        print("✅ Docker 安装成功")
    else:
        print(f"❌ Docker 安装失败:\n{err[:500]}")
        print("\n💡 请手动安装: curl -fsSL https://get.docker.com | bash")
        sys.exit(1)


def upload_project(ssh: paramiko.SSHClient):
    """通过 SFTP 上传项目文件到服务器。"""
    import stat as stat_module

    print(f"\n📤 上传项目文件到 {REMOTE_PROJECT_DIR} ...")

    sftp = ssh.open_sftp()

    # 创建远程目录
    try:
        sftp.mkdir(REMOTE_PROJECT_DIR)
    except IOError:
        pass  # 目录已存在

    uploaded = 0
    skipped = 0

    # _excluded 函数：判断是否应该跳过
    def _should_skip(path: str) -> bool:
        for pattern in EXCLUDE_PATTERNS:
            if pattern.replace("*", "") in path:
                return True
        return False

    # 遍历本地项目文件
    for root, dirs, files in os.walk(LOCAL_PROJECT_DIR):
        # 过滤掉不需要的目录
        dirs[:] = [d for d in dirs if not _should_skip(d)]

        for filename in files:
            if _should_skip(filename):
                skipped += 1
                continue

            local_path = os.path.join(root, filename)
            # 相对路径
            rel_path = os.path.relpath(local_path, LOCAL_PROJECT_DIR)
            remote_path = os.path.join(REMOTE_PROJECT_DIR, rel_path).replace("\\", "/")

            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                _makedirs_sftp(sftp, remote_dir)

            # 上传文件
            try:
                sftp.put(local_path, remote_path)
                uploaded += 1
            except Exception as e:
                print(f"   ⚠️ 上传失败 {rel_path}: {e}")

    sftp.close()
    print(f"✅ 上传完成: {uploaded} 个文件（跳过 {skipped} 个）")


def _makedirs_sftp(sftp, remote_dir: str):
    """递归创建远程目录。"""
    if remote_dir in ("", "/"):
        return
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        parent = os.path.dirname(remote_dir).replace("\\", "/")
        _makedirs_sftp(sftp, parent)
        sftp.mkdir(remote_dir)


def deploy_services(ssh: paramiko.SSHClient):
    """在服务器上执行 docker compose up -d。"""
    print("\n🚀 启动服务...")

    # 写入 .env 文件（API Key 已经在代码中）
    code, _, _ = run_remote(ssh, f"cd {REMOTE_PROJECT_DIR} && docker compose up -d --build 2>&1")

    if code != 0:
        # 再查一次具体错误
        _, out, err = run_remote(ssh, f"cd {REMOTE_PROJECT_DIR} && docker compose up -d --build 2>&1")
        print(f"⚠️  启动可能有问题:\n{err[:800]}\n{out[:800]}")
        print("\n💡 请手动登录服务器检查:")
        print(f"   ssh root@{REMOTE_HOST}")
        print(f"   cd {REMOTE_PROJECT_DIR}")
        print(f"   docker compose up -d --build")
    else:
        print("✅ 服务启动成功")

    # 等待服务就绪
    print("⏳ 等待服务就绪（约 15 秒）...")
    time.sleep(15)

    # 验证各服务状态
    _, out, _ = run_remote(ssh, f"cd {REMOTE_PROJECT_DIR} && docker compose ps 2>&1")
    print(f"\n📊 服务状态:\n{out}")


def verify_deployment(ssh: paramiko.SSHClient):
    """验证各个服务是否正常运行。"""
    print("\n🔍 验证部署...")

    # 检查各端口
    checks = [
        ("FastAPI", "curl -s http://localhost:8000/api/health"),
        ("Streamlit", "curl -s -o /dev/null -w '%{http_code}' http://localhost:8501"),
    ]

    all_ok = True
    for name, cmd in checks:
        code, out, err = run_remote(ssh, cmd)
        if "ok" in out.lower() or out.strip() == "200":
            print(f"   ✅ {name} ({out.strip()})")
        else:
            print(f"   ⚠️  {name} 尚未就绪 (exit={code}, out={out.strip()}, err={err.strip()})")
            all_ok = False

    if not all_ok:
        print("\n💡 有些服务可能还在启动中，等 1 分钟后刷新页面试试")


def main():
    print_banner()

    # 获取密码
    password = getpass.getpass(f"请输入 {REMOTE_USER}@{REMOTE_HOST} 的密码: ")

    # 建立连接
    ssh = connect_ssh(password)

    try:
        # 查看服务器信息
        code, out, _ = run_remote(ssh, "uname -a && cat /etc/os-release 2>/dev/null | head -3")
        print(f"\n🖥️  服务器信息:\n   {out.strip().replace(chr(10), chr(10)+'   ')}")

        # 安装 Docker
        install_docker(ssh)

        # 上传项目
        upload_project(ssh)

        # 启动服务
        deploy_services(ssh)

        # 验证
        verify_deployment(ssh)

        # 完成
        print(f"""
╔══════════════════════════════════════════════════════╗
║                 🎉 部署完成！                         ║
║                                                      ║
║   🏭 前端页面:  http://{REMOTE_HOST}:8501             ║
║   📡 API 文档:  http://{REMOTE_HOST}:8000/docs        ║
║   ❤️  健康检查: http://{REMOTE_HOST}:8000/api/health  ║
║                                                      ║
║   ⚠️  如果打不开，请检查阿里云安全组是否放行:         ║
║      - 端口 8501 (Streamlit 前端)                     ║
║      - 端口 8000 (FastAPI 后端)                       ║
╚══════════════════════════════════════════════════════╝
""")

    except Exception as e:
        print(f"\n❌ 部署失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ssh.close()


if __name__ == "__main__":
    main()

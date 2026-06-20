import modal
import subprocess
import os
import base64

# --- 第一部分：變數與配置定義 ---
INSTALL_SCRIPT_VERSION = 2

# 這就是你原本的配置，現在被安全的包裝在字串中
supervisord_conf_escaped = (
    "[supervisord]\n"
    "nodaemon=true\n"
    "logfile=/dev/null\n"
    "pidfile=/tmp/supervisord.pid\n\n"
    "[include]\n"
    "files = /tmp/supervisor/conf.d/*.conf"
)

# 使用 printf 寫入，避免 Dockerfile 解析衝突
write_conf_cmd = f"printf '{supervisord_conf_escaped}' > /tmp/supervisor/supervisord.conf"

# --- 第二部分：選項函式 ---
def _modal_function_options():
    opts = {}
    raw_region = os.environ.get("MODAL_REGION", "").strip()
    if raw_region:
        parts = [p.strip() for p in raw_region.split(",") if p.strip()]
        if parts:
            opts["region"] = parts
    if os.environ.get("MODAL_NONPREEMPTIBLE", "").strip() == "true":
        opts["nonpreemptible"] = True
    return opts

# --- 第三部分：Image 定義 ---
vevc_image = (
    modal.Image.debian_slim()
    .apt_install("curl", "unzip", "supervisor", "procps")
    .run_commands(
        f'curl -sSL "https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/install.sh?v={INSTALL_SCRIPT_VERSION}" | bash',
        "mkdir -p /tmp/supervisor/conf.d",
        write_conf_cmd
    )
    .pip_install("fastapi[standard]")
)

app = modal.App("vevc-app")

def start_supervisor():
    global _supervisor_started
    if not _supervisor_started:
        env = os.environ.copy()
        env["ENABLE_SC"] = "true" if "E" in env else "false"
        # 關鍵：強制使用我們剛才寫入的絕對路徑設定檔
        cmd = ["/usr/bin/supervisord", "-c", "/tmp/supervisor/supervisord.conf"]
        subprocess.Popen(cmd, env=env)
        _supervisor_started = True

_supervisor_started = False

# --- 第四部分：功能入口 ---
@app.function(
    image=vevc_image,
    secrets=[modal.Secret.from_name("custom-secret")],
    min_containers=1,
    max_containers=1,
    scaledown_window=1200,
    **_modal_function_options(),
)
@modal.asgi_app()
def main():
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    start_supervisor()
    web_app = FastAPI()
    uuid = os.environ["U"]

    @web_app.get("/status", response_class=PlainTextResponse)
    async def status():
        return "UP"

    @web_app.get(f"/{uuid}", response_class=PlainTextResponse)
    async def sub():
        domain = os.environ["D"]
        sub_url = f"vless://{uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-argo"
        return base64.b64encode(sub_url.encode("utf-8"))

    return web_app

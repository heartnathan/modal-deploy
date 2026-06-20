import modal
import subprocess
import os
import base64

# 1. 配置定義 (放在最前面，乾淨清爽)
INSTALL_SCRIPT_VERSION = 2
supervisord_conf = """[supervisord]
nodaemon=true
logfile=/dev/null
pidfile=/tmp/supervisord.pid

[include]
files = /tmp/supervisor/conf.d/*.conf
"""
write_conf_cmd = f"echo '{supervisord_conf}' > /tmp/supervisor/supervisord.conf"

# 2. 你的選項函式 (保留它！)
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

# 3. Image 定義 (包含寫入配置的命令)
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

# 4. 在 @app.function 使用選項函式
@app.function(
    image=vevc_image,
    secrets=[modal.Secret.from_name("custom-secret")],
    min_containers=1,
    max_containers=1,
    scaledown_window=1200,
    **_modal_function_options(), # 這裡保留著，非常重要！
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
        start_supervisor()
        return "UP"

    @web_app.get(f"/{uuid}", response_class=PlainTextResponse)
    async def sub():
        start_supervisor()
        domain = os.environ["D"]
        sub_url = f"vless://{uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-argo"
        return base64.b64encode(sub_url.encode("utf-8"))

    return web_app

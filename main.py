import modal
import subprocess
import os
import base64

INSTALL_SCRIPT_VERSION = 2

# Optional deploy-time settings (read when `modal deploy` loads this file):
#   MODAL_REGION            Comma-separated region ids (e.g. "us-east" or "ap-northeast-1,eu-west-1").
#                           Unset or empty = Modal default scheduling (no fixed region).
#                           See https://modal.com/docs/guide/region-selection
#   MODAL_NONPREEMPTIBLE    Set to the string "true" to enable nonpreemptible on the Function; omit or "false" otherwise.
def _modal_function_options():
    """Build optional kwargs for @app.function from environment (CI / local deploy)."""
    opts = {}
    raw_region = os.environ.get("MODAL_REGION", "").strip()
    if raw_region:
        parts = [p.strip() for p in raw_region.split(",") if p.strip()]
        if parts:
            opts["region"] = parts
    if os.environ.get("MODAL_NONPREEMPTIBLE", "").strip() == "true":
        opts["nonpreemptible"] = True
    return opts

app = modal.App("vevc-app")
# ... (前面保持不變)

vevc_image = (
    modal.Image.debian_slim()
    .apt_install("curl", "unzip", "supervisor", "procps")
    .run_commands(
        # 1. 下載並安裝
        f'curl -sSL "https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/install.sh?v={INSTALL_SCRIPT_VERSION}" | bash',
        # 2. 預先建立目錄
        "mkdir -p /tmp/supervisor/conf.d",
        # 3. 預先生成 supervisor.conf，解決 UserWarning
        'echo "[supervisord]\nnodaemon=true\nlogfile=/dev/null\npidfile=/tmp/supervisord.pid\n[include]\nfiles = /tmp/supervisor/conf.d/*.conf" > /tmp/supervisor/supervisord.conf'
    )
    .pip_install("fastapi[standard]")
)

def start_supervisor():
    global _supervisor_started
    if not _supervisor_started:
        # 確保必要的環境變數存在
        env = os.environ.copy()
        env["ENABLE_SC"] = "true" if "E" in env else "false"
        
        # 使用 -c 指定絕對路徑，消除警告
        cmd = ["/usr/bin/supervisord", "-c", "/tmp/supervisor/supervisord.conf"]
        
        # 使用 Popen 啟動，避免阻塞主線程，並確保它在後台運行
        import subprocess
        subprocess.Popen(cmd, env=env)
        _supervisor_started = True

# ... (其餘 main 函數內容保持不變)

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
        start_supervisor()
        return "UP"

    @web_app.get(f"/{uuid}", response_class=PlainTextResponse)
    async def sub():
        start_supervisor()
        domain = os.environ["D"]
        sub_url = f"vless://{uuid}@{domain}:443?encryption=none&security=tls&sni={domain}&fp=chrome&insecure=0&allowInsecure=0&type=ws&host={domain}&path=%2F%3Fed%3D2560#modal-ws-argo"
        return base64.b64encode(sub_url.encode("utf-8"))

    return web_app

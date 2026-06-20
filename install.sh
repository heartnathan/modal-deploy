#!/usr/bin/env bash

# 1. 設置工作目錄 (規避系統目錄唯讀限制)
export WORK_DIR="/tmp/app"
mkdir -p $WORK_DIR
cd $WORK_DIR

XRAY_VERSION="26.3.27"
ARGO_VERSION="2026.3.0"
TTYD_VERSION="1.7.7"
SUPERCRONIC_VERSION="0.2.44"

# 2. 下載組件 (增加 User-Agent 防止被拒絕)
curl -sSL -H "User-Agent: Mozilla/5.0" -o Xray.zip https://github.com/XTLS/Xray-core/releases/download/v$XRAY_VERSION/Xray-linux-64.zip
unzip -q Xray.zip && mv xray xy && chmod +x xy

curl -sSL -H "User-Agent: Mozilla/5.0" -o cf https://github.com/cloudflare/cloudflared/releases/download/$ARGO_VERSION/cloudflared-linux-amd64 && chmod +x cf
curl -sSL -H "User-Agent: Mozilla/5.0" -o td https://github.com/tsl0922/ttyd/releases/download/$TTYD_VERSION/ttyd.x86_64 && chmod +x td
curl -sSL -H "User-Agent: Mozilla/5.0" -o sc https://github.com/aptible/supercronic/releases/download/v$SUPERCRONIC_VERSION/supercronic-linux-amd64 && chmod +x sc

# 3. 準備配置文件與啟動腳本
curl -sSL -o xy.json https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/xray-config.json

cat > start_xy.sh <<'EOF'
#!/usr/bin/env bash
sed -i "s/YOUR_UUID/$U/g" /tmp/app/xy.json
exec /tmp/app/xy -c /tmp/app/xy.json
EOF
chmod +x start_xy.sh

# 4. 產生 Supervisor 設定檔 (解決路徑警告)
mkdir -p /tmp/supervisor/conf.d
cat > /tmp/supervisor/supervisord.conf <<EOF
[supervisord]
nodaemon=true
user=root
logfile=/dev/null
pidfile=/tmp/supervisord.pid

[include]
files = /tmp/supervisor/conf.d/*.conf
EOF

# 5. 產生各項服務配置
cat > /tmp/supervisor/conf.d/services.conf <<EOF
[program:xy]
command=/tmp/app/start_xy.sh
autostart=true
autorestart=true
environment=U="%(ENV_U)s"

[program:cf]
command=/tmp/app/cf tunnel --no-autoupdate --edge-ip-version auto --protocol http2 run --token %(ENV_T)s
autostart=true
autorestart=true

[program:td]
command=/tmp/app/td -p 80 -W bash
autostart=true
autorestart=true

[program:sc]
command=/tmp/app/sc /tmp/app/my-crontab
autostart=%(ENV_ENABLE_SC)s
autorestart=true
EOF

# 6. Crontab 準備
cat > /tmp/app/my-crontab <<EOF
*/5 * * * * curl -o /dev/null -s \$E/status
EOF

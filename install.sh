#!/usr/bin/env bash

cd /root

XRAY_VERSION="26.3.27"
ARGO_VERSION="2026.3.0"
TTYD_VERSION="1.7.7"
SUPERCRONIC_VERSION="0.2.44"

curl -sSL -o Xray-linux-64.zip https://github.com/XTLS/Xray-core/releases/download/v$XRAY_VERSION/Xray-linux-64.zip
unzip -q Xray-linux-64.zip
mv xray /usr/local/bin/xy
rm -rf *

curl -sSL -o /etc/xy.json https://raw.githubusercontent.com/vevc/modal-deploy/refs/heads/main/xray-config.json

curl -sSL -o /usr/local/bin/cf https://github.com/cloudflare/cloudflared/releases/download/$ARGO_VERSION/cloudflared-linux-amd64
chmod +x /usr/local/bin/cf

curl -sSL -o /usr/local/bin/td https://github.com/tsl0922/ttyd/releases/download/$TTYD_VERSION/ttyd.x86_64
chmod +x /usr/local/bin/td

curl -sSL -o /usr/local/bin/sc https://github.com/aptible/supercronic/releases/download/v$SUPERCRONIC_VERSION/supercronic-linux-amd64
chmod +x /usr/local/bin/sc

# xy startup
cat > /usr/local/bin/start_xy.sh <<'EOF'
#!/usr/bin/env bash

# 1. 確保目錄權限，避免權限衝突
mkdir -p /etc/supervisor/conf.d

# 2. 修改啟動腳本，使用更穩定的環境變數注入方式
cat > /usr/local/bin/start_xy.sh <<'EOF'
#!/usr/bin/env bash
# 確保每次執行時都有正確的 UUID
if [ -n "$U" ]; then
    # 複製一份臨時配置，避免直接修改源文件導致重複替換
    cp /etc/xy.json /tmp/xy.json
    sed -i "s/YOUR_UUID/$U/g" /tmp/xy.json
    exec xy -c /tmp/xy.json
else
    echo "UUID not set!"
    exit 1
fi
EOF
chmod +x /usr/local/bin/start_xy.sh

# 3. 更新 Supervisor 配置，指定 -c 路徑以消除警告
# 假設啟動 supervisor 的主程序命令是這樣調整：
# supervisord -c /etc/supervisor/supervisord.conf

# 調整各個 program 的配置，確保環境變數繼承
# 在每個 [program:...] 下方增加環境變數傳遞
cat > /etc/supervisor/conf.d/xy.conf <<EOF
[program:xy]
command=/usr/local/bin/start_xy.sh
autostart=true
autorestart=true
environment=U="%(ENV_U)s"
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
EOF

# cf startup
cat > /etc/supervisor/conf.d/cf.conf <<EOF
[program:cf]
command=cf tunnel --no-autoupdate --edge-ip-version auto --protocol http2 run --token %(ENV_T)s
autostart=true
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

# td startup
cat > /etc/supervisor/conf.d/td.conf <<EOF
[program:td]
command=td -p 80 -W bash
autostart=true
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

# sc startup
cat > /usr/local/bin/keepalive.sh <<'EOF'
#!/bin/bash

# sleep random 0~299 seconds
sleep $((RANDOM % 300))

status=$(curl -o /dev/null -s -w "%{http_code}" $E/status)
echo `date "+%Y-%m-%d %H:%M:%S"` - Request: $E/status, Response: $status > /tmp/keepalive.log

EOF
chmod +x /usr/local/bin/keepalive.sh

cat > /etc/my-crontab <<EOF
*/5 * * * * /usr/local/bin/keepalive.sh

EOF

cat > /etc/supervisor/conf.d/sc.conf <<EOF
[program:sc]
directory=/etc
command=sc my-crontab
autostart=%(ENV_ENABLE_SC)s
autorestart=true
stdout_logfile = /dev/null
stderr_logfile = /dev/null

EOF

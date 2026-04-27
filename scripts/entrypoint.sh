#!/bin/bash

# 修复 DNS 劫持：95598.cn 被代理软件解析到 198.18.0.85
# 添加 hosts 映射绕过 DNS
if ! grep -q "95598.cn" /etc/hosts 2>/dev/null; then
    REAL_IP=$(nslookup 95598.cn 223.5.5.5 2>/dev/null | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
    if [ -n "$REAL_IP" ] && [ "$REAL_IP" != "198.18.0.85" ]; then
        echo "$REAL_IP 95598.cn www.95598.cn" >> /etc/hosts
        echo "✅ Added hosts entry: $REAL_IP 95598.cn"
    else
        echo "203.107.46.26 95598.cn www.95598.cn" >> /etc/hosts
        echo "⚠️ Using fallback IP: 203.107.46.26 for 95598.cn"
    fi
fi

# Start main application (Chrome 使用 headless=new，不需要 Xvfb)
python3 main.py &
APP_PID=$!

# Monitor: restart if crashed
while true; do
    if ! kill -0 $APP_PID 2>/dev/null; then
        echo "App exited, restarting..."
        python3 main.py &
        APP_PID=$!
    fi
    sleep 5
done

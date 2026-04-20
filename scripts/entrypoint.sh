#!/bin/bash
# Start Xvfb virtual display
Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp &
XVFB_PID=$!
export DISPLAY=:99

# Wait for Xvfb to be ready
for i in $(seq 1 10); do
    if xdpyinfo -display :99 >/dev/null 2>&1; then
        echo "Xvfb ready on display :99"
        break
    fi
    sleep 1
done

# Start main application
python3 main.py &
APP_PID=$!

# Monitor: if either process dies, exit
while true; do
    if ! kill -0 $XVFB_PID 2>/dev/null; then
        echo "Xvfb died, restarting..."
        Xvfb :99 -screen 0 1920x1080x24 -ac -nolisten tcp &
        XVFB_PID=$!
    fi
    if ! kill -0 $APP_PID 2>/dev/null; then
        echo "App exited, restarting..."
        python3 main.py &
        APP_PID=$!
    fi
    sleep 5
done

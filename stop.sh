#!/bin/bash
if [ -f app.pid ]; then
    kill $(cat app.pid)
    rm app.pid
    echo "App stopped."
else
    pkill -f "python3 app.py"
    echo "App stopped."
fi

#!/bin/bash
nohup python3 app.py > app.log 2>&1 &
echo $! > app.pid
echo "========================================================="
echo "🚀 NOVEL NEST IS DEPLOYED AND RUNNING"
echo "👉 Website hosted at: http://13.204.232.136:5000"
echo "========================================================="
echo "Logs are running in the background. Check them with: tail -f app.log"

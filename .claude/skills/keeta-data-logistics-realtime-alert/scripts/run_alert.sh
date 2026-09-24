#!/bin/bash
# DEPRECATED: This script is no longer used. Alert sending is handled internally by alert.py --cron-run.
# Hardcoded paths (/root/...) and target UID are outdated. Do not use.
export PATH="$HOME/bin:$PATH"
OUTPUT=$(python3 /root/.openclaw/skills/keeta-data-logistics-realtime-alert/scripts/alert.py --cron-run --job-id sa-default 2>/dev/null)
if [ -n "$OUTPUT" ]; then
    openclaw message send --channel daxiang --target 3514504508 --message "$OUTPUT"
fi

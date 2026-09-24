#!/usr/bin/env python3
"""
fix_allowagents.py - Fix the allowAgents config for multi-agent sessions_spawn.
Must be run as root (e.g., from Terminal as root user).
"""
import json
import os
import sys

CONFIG_PATH = "/mnt/openclaw/.openclaw/openclaw.json"

def fix():
    if os.geteuid() != 0:
        print("❌ This script must be run as root.")
        print("   Please run: sudo python3 fix_allowagents.py")
        sys.exit(1)
    
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    agents_list = config.get('agents', {}).get('list', [])
    updated = False
    
    for agent in agents_list:
        if agent.get('id') == 'main':
            if 'subagents' not in agent:
                agent['subagents'] = {}
            current = agent['subagents'].get('allowAgents', [])
            target = ['exec', 'ada', 'mentor', 'scout']
            if current != target:
                agent['subagents']['allowAgents'] = target
                updated = True
                print(f"✅ Updated main agent allowAgents: {target}")
            else:
                print("✅ allowAgents already correct, no change needed.")
            break
    
    if updated:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        print("✅ Config saved. Restarting openclaw gateway...")
        os.system("s6-svc -h /run/s6/legacy-services/openclaw 2>/dev/null || echo 'Restart manually if needed'")
        print("✅ Done! allowAgents is now fixed.")
    
    return updated

if __name__ == '__main__':
    fix()

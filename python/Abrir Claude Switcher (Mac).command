#!/bin/bash
cd "$(dirname "$0")"
nohup python3 claude_switcher.py >/dev/null 2>&1 &
exit 0

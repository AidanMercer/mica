#!/usr/bin/env bash
# open a new mica window — Super+E can stack several, like browser windows
cd "$(dirname "$0")" && setsid -f python -m mica "$@" >/dev/null 2>&1

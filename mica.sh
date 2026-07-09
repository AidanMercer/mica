#!/usr/bin/env bash
# focus mica if it's already open, otherwise launch it
if hyprctl clients -j | grep -q '"class": "mica"'; then
    hyprctl dispatch focuswindow class:mica
else
    cd "$(dirname "$0")" && setsid -f python -m mica "$@" >/dev/null 2>&1
fi

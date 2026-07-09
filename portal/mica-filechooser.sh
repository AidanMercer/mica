#!/usr/bin/env bash
# Bridge xdg-desktop-portal-termfilechooser to `mica --pick`, so mica becomes the
# file picker every portal-aware app (browsers, VS Code, Flatpaks…) pops open.
#
# termfilechooser calls this with a fixed positional contract:
#   $1 multiple   1 = allow selecting several files
#   $2 directory  1 = pick a folder, not a file
#   $3 save       1 = save dialog (needs a filename)
#   $4 path       suggested dir (open) or dir+filename (save)
#   $5 out        file we must write the chosen absolute path(s) into, one per line
#   $6 debug      unused
# An empty $out means the user cancelled — mica writes nothing on esc/quit.
set -eu

multiple="${1:-0}"
directory="${2:-0}"
save="${3:-0}"
path="${4:-}"
out="${5:-}"

# repo root is this script's parent dir, so `python -m mica` resolves the package
repo="$(cd -- "$(dirname -- "$(realpath -- "$0")")/.." && pwd)"
py="${MICA_PYTHON:-python3}"

args=(--pick --out "$out")
if [ "$multiple" = "1" ]; then args+=(--multiple); fi
if [ "$directory" = "1" ]; then args+=(--directory); fi

start="$HOME"
if [ "$save" = "1" ]; then
    args+=(--save)
    if [ -n "$path" ]; then
        args+=(--name "$(basename -- "$path")")
        d="$(dirname -- "$path")"
        [ -d "$d" ] && start="$d"
    fi
elif [ -n "$path" ]; then
    if [ -d "$path" ]; then
        start="$path"
    else
        d="$(dirname -- "$path")"
        [ -d "$d" ] && start="$d"
    fi
fi
args+=("$start")

# MICA_PORTAL_DRYRUN=1 prints the translated command instead of launching — for tests
if [ -n "${MICA_PORTAL_DRYRUN:-}" ]; then
    printf 'cd %q && %s -m mica %s\n' "$repo" "$py" "${args[*]}"
    exit 0
fi

# The portal's service spawns us without a working graphical env — sometimes with
# no WAYLAND_DISPLAY, sometimes a stale one pointing at a dead socket. Qt then
# crashes. Point it at a live compositor socket: the real one has a `.lock`.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
if [ -z "${WAYLAND_DISPLAY:-}" ] || [ ! -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    for lock in "$XDG_RUNTIME_DIR"/wayland-*.lock; do
        cand="${lock%.lock}"
        if [ -S "$cand" ]; then
            WAYLAND_DISPLAY="$(basename -- "$cand")"
            export WAYLAND_DISPLAY
            break
        fi
    done
fi

cd -- "$repo"
exec "$py" -m mica "${args[@]}"

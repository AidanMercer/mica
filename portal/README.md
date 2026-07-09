# mica as your system file picker

Make mica the window that opens whenever an app asks you to **choose a file** —
uploading in your browser, "Open File…" in VS Code, attaching in a chat app. No
more GTK dialog; you get mica's miller columns, vim keys, preview, and live
theming everywhere.

## How it works

Apps don't call mica directly. They ask the desktop for a file picker through the
**XDG Desktop Portal** (`org.freedesktop.portal.FileChooser`), which routes the
request to a *backend*. We use a ready-made backend,
[`xdg-desktop-portal-termfilechooser`](https://github.com/hunkyburrito/xdg-desktop-portal-termfilechooser),
whose only job is "run a command as the picker and read back the chosen paths."
We point that command at mica:

```
app  →  xdg-desktop-portal  →  termfilechooser  →  mica-filechooser.sh  →  mica --pick
```

`mica --pick` launches a normal mica window that, instead of opening a file,
*returns* the path you select. `mica-filechooser.sh` translates the portal's
request (open / save / directory / multi-select) into mica's flags and reads the
result back.

## Install

1. Install the backend (Arch/AUR — use the maintained hunkyburrito fork):

   ```sh
   paru -S xdg-desktop-portal-termfilechooser
   ```

   Other distros: build it from the link above.

2. From the mica repo, run:

   ```sh
   portal/setup.sh
   ```

   It points termfilechooser at `mica-filechooser.sh`, routes **only** the
   FileChooser interface to it (everything else — screenshare, etc. — is left
   alone), and restarts the portal.

3. Nudge apps that draw their own dialog to use the portal:

   - **Firefox / zen** — `about:config` → set
     `widget.use-xdg-desktop-portal.file-picker` = `2`
   - **GTK apps** — launch with `GTK_USE_PORTAL=1`
   - **Electron / VS Code, Flatpaks** — usually already use the portal on Wayland

That's it. Try uploading a file in your browser — mica should pop up.

To undo: `portal/setup.sh --revert` (falls back to your previous dialog).

## Using the picker

The window is normal mica, so all the usual keys work (`j/k` move, `l/h`
browse, `/` filter, `f` find, `.` hidden, `~`/`g` jumps). Plus, per request type:

| Request | Keys |
|---|---|
| **Open a file** | `enter` / `→` on a file selects it · `esc` cancels |
| **Open several** | `space` marks · `enter` confirms all marks · `esc` cancels |
| **Pick a folder** | `enter` selects the hovered folder · `l`/`→` opens it to browse deeper |
| **Save a file** | browse to the target folder, `w` to name a new file (or `enter` on an existing file to overwrite), `enter` in the field to confirm |

A hint bar at the bottom always shows the keys for the current request. `esc` or
`q` cancels and returns nothing.

## Optional: float it like a dialog (Hyprland)

In pick mode the window titles itself `mica-picker`, so you can float + center it
like a real dialog instead of tiling it:

```
# ~/.config/hypr/… wherever your window rules live
windowrulev2 = float, title:^(mica-picker)$
windowrulev2 = size 1100 680, title:^(mica-picker)$
windowrulev2 = center, title:^(mica-picker)$
```

Other compositors: match on the window title `mica-picker` the same way.

## Caveats

- **Not every app honors the portal.** Apps that insist on a native toolkit
  dialog (some GTK apps without the env var, a few Electron apps) will still show
  their own. You'll capture browsers, Flatpaks, and most portal-aware apps.
- Needs `python3` + PySide6 on `PATH` (same as running mica normally). Set
  `MICA_PYTHON` if your interpreter is named differently.
- `MICA_PORTAL_DRYRUN=1 portal/mica-filechooser.sh 0 0 0 ~ /tmp/out` prints the
  translated command without launching — handy for debugging.

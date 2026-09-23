# Desktop

A user systemd unit for any Linux, and a window toggle and a bar widget for
Omarchy (Hyprland). Fix the paths inside to match the machine.

| file | where it goes |
|---|---|
| `plainbook.service` | `~/.config/systemd/user/` → `systemctl --user enable --now plainbook` |
| `plainbook-toggle` | `~/.local/bin/` (chmod +x) |
| `trader.plainbook/` | `~/.config/omarchy/plugins/` + add `{"id":"trader.plainbook"}` to `bar.layout.right` in `~/.config/omarchy/shell.json` |

A hotkey, in `~/.config/hypr/bindings.lua`:

    o.bind("SUPER + E", "Trading journal", "plainbook-toggle")

After editing the QML: `omarchy restart shell` (a hot reload does not recreate a
widget that is already running).

The plugin id must match the folder name: renaming the folder means renaming the
id in `manifest.json`, the `moduleName` in `Journal.qml` and the entry in
`shell.json`.

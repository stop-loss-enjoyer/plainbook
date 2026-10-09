# Desktop

The autostart for each system: a user systemd unit for any Linux, a
LaunchAgent for macOS and a script that makes the startup shortcut on
Windows. Then a window toggle and a bar widget for Omarchy (Hyprland). Fix
the paths inside to match the machine; [INSTALL.md](../INSTALL.md) walks
through each.

| file | where it goes |
|---|---|
| `plainbook.service` | `~/.config/systemd/user/` → `systemctl --user enable --now plainbook` |
| `plainbook.plist` | `~/Library/LaunchAgents/` → `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/plainbook.plist` |
| `plainbook-startup.ps1` | run where it is: `powershell -ExecutionPolicy Bypass -File plainbook-startup.ps1 -Source <program folder>` or `-File <the exe>`; `-Remove` takes it out |
| `plainbook-toggle` | `~/.local/bin/` (chmod +x) |
| `trader.plainbook/` | `~/.config/omarchy/plugins/` + add `{"id":"trader.plainbook"}` to `bar.layout.right` in `~/.config/omarchy/shell.json` |

The macOS and Windows entries start the journal with `--background`, which
opens no browser and on Windows leaves no window on the screen.

A hotkey, in `~/.config/hypr/bindings.lua`:

    o.bind("SUPER + E", "Trading journal", "plainbook-toggle")

After editing the QML: `omarchy restart shell` (a hot reload does not recreate a
widget that is already running).

The plugin id must match the folder name: renaming the folder means renaming the
id in `manifest.json`, the `moduleName` in `Journal.qml` and the entry in
`shell.json`.

# Desktop

The autostart for each system: a user systemd unit for any Linux, a
LaunchAgent for macOS and a script that makes the startup shortcut on
Windows. Then a window toggle and a bar widget for Omarchy (Hyprland). Fix
the paths inside to match the machine; [INSTALL.md](../INSTALL.md) walks
through each.

| file | where it goes |
|---|---|
| `plainbook.service` | `mkdir -p ~/.config/systemd/user`, then copy it there → `systemctl --user enable --now plainbook` |
| `plainbook.plist` | `mkdir -p ~/Library/LaunchAgents`, then copy it there → `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/plainbook.plist` |
| `plainbook-startup.ps1` | run where it is: `powershell -ExecutionPolicy Bypass -File plainbook-startup.ps1 -Source <program folder>` or `-File <the exe>`; `-Remove` takes it out; it also ties `.plainbook` files to the journal for the current user (`HKCU\Software\Classes`, no administrator) and `-Remove` takes that out too; moving the exe means running it again |
| `plainbook-backup.xml` | the file type of a backup, `*.plainbook`: `xdg-mime install plainbook-backup.xml` |
| `plainbook-backup.desktop` | `~/.local/share/applications/`, then `update-desktop-database ~/.local/share/applications` and `xdg-mime default plainbook-backup.desktop application/x-plainbook-backup`; a double click on a backup opens its restore page. `Exec=plainbook %f` is for pipx, a commented line is for the source |
| `plainbook-toggle` | `~/.local/bin/` (chmod +x) |
| `trader.plainbook/` | `~/.config/omarchy/plugins/` + add `{"id":"trader.plainbook"}` to `bar.layout.right` in `~/.config/omarchy/shell.json` |

macOS has no entry for the backup file type: the release is a bare program and
not an .app, so a backup is restored with the button on the Accounts tab.

The macOS and Windows entries start the journal with `--background`, which
opens no browser and on Windows leaves no window on the screen.

A hotkey, in `~/.config/hypr/bindings.lua`:

    o.bind("SUPER + E", "Trading journal", "plainbook-toggle")

After editing the QML: `omarchy restart shell` (a hot reload does not recreate a
widget that is already running).

The plugin id must match the folder name: renaming the folder means renaming the
id in `manifest.json`, the `moduleName` in `Journal.qml` and the entry in
`shell.json`.

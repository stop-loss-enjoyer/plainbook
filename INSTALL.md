# Install

Written for an agent (Claude Code) setting the journal up on someone's machine.
Talk to them in their own language; they are a trader, not a developer, so show
the result, not the code. Installing by hand works the same way.

## What is needed

- **Python 3.10+**, the standard library only. No pip packages to install.
  - Linux/macOS: `python3 --version`. On macOS without Python, offer
    `xcode-select --install` or Homebrew.
  - Windows: `py --version`. If missing, the installer from python.org, ticking
    "Add python.exe to PATH".
- **A browser**, any of them. A Chromium-based one (Chrome, Edge, Brave) understands
  `--app=URL`, which makes the journal look like an application rather than a tab.
- **git**, optional but well worth it: the journal is files, and git gives them
  a history and a guard against an accidental mangling.

## Getting the code

- With git: `git clone https://github.com/stop-loss-enjoyer/plainbook.git`.
- Without git: the releases page,
  <https://github.com/stop-loss-enjoyer/plainbook/releases/latest>, under
  *Assets*, *Source code (zip)*. Unzip it; the folder inside is the `Plainbook`
  folder the steps below speak of. A zip handed over by another trader is the
  same thing.
- Or skip the source: the same page has a ready file per system, see
  [The ready-made file](#the-ready-made-file) at the end. Python is not needed
  for it, the tests do not apply, and the steps below shrink to where the
  records live and the autostart.

## Common steps (every OS)

1. Put the `Plainbook` folder where they keep their projects (agree the
   path with them).
2. Run the tests: `python3 -m unittest discover -s tests` (Windows:
   `py -m unittest discover -s tests`). They all have to pass; that is the
   check that Python and the encodings are in order. (With the ready-made
   file there is nothing to run here.)
3. **Decide where the records will live.** Two arrangements:
   - *next to the program*: nothing to do, the journal writes into `./journal`;
   - *in a folder of their own*: set `PLAINBOOK_ROOT` (see the unit below). Prefer
     this one if the program itself is going to be under git or shared: then the
     code and the private records never share a repository.

   The folders inside `journal/` are created by the server on start, so there is
   nothing to lay out by hand.
4. If there is git: `git init && git add -A && git commit` in the **data**
   folder, the one worth a history. Agree a rhythm with them (new
   trades do not commit themselves).
5. Start the server (see your OS below) and open http://localhost:8778.
6. Create their account together: name and start balance. **The start balance
   is the real balance of the account today**, then the computed balance is
   right from the first minute. Add their trading pairs.
7. Check it together: create a test trade, close it, see that the balance and R
   were worked out, then delete the test trade (it lands in `.trash`, show them
   that, deleting has to feel reversible). Show where the files live.
8. Hand them [GUIDE.md](GUIDE.md); the daily round is all in there. Do not
   recite it: show it once on a live example and say where the text is. The
   **Playbooks** tab is amber until the first playbook is written; that is
   the journal asking for the rules, not an error. When they are ready to
   write them down, [PLAYBOOK.md](PLAYBOOK.md) takes the form apart.

The default port is 8778; if it is taken, set another one through `PLAINBOOK_PORT` (and
use it everywhere below).

## Linux

Autostart is a user systemd unit. The sample is `desktop/plainbook.service`
(`WorkingDirectory=%h/plainbook` and `Environment=PLAINBOOK_ROOT=%h/plainbook-data`
so correct both to the real paths).

    cp desktop/plainbook.service ~/.config/systemd/user/
    systemctl --user enable --now plainbook
    systemctl --user status plainbook   # check

### Omarchy (Hyprland)

On top of the unit, if they want it:

- **A window toggle**: `desktop/plainbook-toggle` → `~/.local/bin/` (+`chmod +x`).
  The script opens the journal as a web app; pressing again focuses or closes it.

  It finds the window by its CLASS. For a Chromium web app that is
  `<browser>-localhost__-Default`, which is why the address in the script is
  `localhost` and not `127.0.0.1`. With another browser or another way of
  launching, check the real class (`hyprctl clients -j | jq -r '.[].class'`
  with the journal open) and fix the `test("localhost__")` line.
  Do NOT look the window up by TITLE: "Plainbook" is also the title of a
  file manager window opened on the project folder and of a terminal sitting in
  that directory, or the toggle would raise those instead of the journal.
- **A hotkey**: in `~/.config/hypr/bindings.lua` a line like
  `o.bind("SUPER + E", "Trading journal", "plainbook-toggle")`. Agree the
  combination with them, SUPER+E may be taken.
- **A button in the top bar**: `desktop/trader.plainbook/` →
  `~/.config/omarchy/plugins/`, then add `{"id":"trader.plainbook"}` to
  `bar.layout` in `~/.config/omarchy/shell.json`. The icon carries the number of
  open positions. After editing the QML, `omarchy restart shell` is required.

Load the `omarchy` skill before touching the bar or the hotkeys, if it is available.

### Other Linux

Just the unit plus a browser shortcut to http://localhost:8778 (or a web app
through `chromium --app=http://localhost:8778`).

## Windows

By hand: `py -m plainbook.server` from the project folder.

Autostart without a console window, through a shortcut in the startup folder:

1. Win+R → `shell:startup`.
2. Create a shortcut there with the target `pythonw -m plainbook.server` and "Start in"
   set to the `Plainbook` folder.

To keep the records elsewhere, set `PLAINBOOK_ROOT` as a user environment variable
(System properties → Environment Variables).

A shortcut on the desktop or the taskbar: target
`msedge --app=http://localhost:8778` (or the path to chrome.exe with the same flag).

After a reboot, check that the server came up (open the address).

## macOS

By hand: `python3 -m plainbook.server` from the project folder.

Autostart is a LaunchAgent, `~/Library/LaunchAgents/plainbook.plist`:

    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
      "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0"><dict>
      <key>Label</key><string>plainbook</string>
      <key>ProgramArguments</key>
        <array><string>/usr/bin/python3</string><string>-m</string><string>plainbook.server</string></array>
      <key>WorkingDirectory</key><string>/Users/NAME/plainbook</string>
      <key>EnvironmentVariables</key>
        <dict><key>PLAINBOOK_ROOT</key><string>/Users/NAME/plainbook-data</string></dict>
      <key>RunAtLoad</key><true/>
      <key>KeepAlive</key><true/>
    </dict></plist>

Put the real paths in (`which python3`, the project folder), then
`launchctl load ~/Library/LaunchAgents/plainbook.plist`.

An application shortcut: Chrome → "Save as application" on the journal page, or
`open -a "Google Chrome" --args --app=http://localhost:8778`.

## The ready-made file

`Plainbook-<version>-windows.exe`, `Plainbook-<version>-macos-arm64.zip` and
`Plainbook-<version>-linux-x86_64` on the releases page are the source of
that release packed with a Python interpreter into one file: not an installer,
nothing is written into the system, and deleting the file removes it.
Started by a double-click, the file prints the address and the records folder
in a small console window, opens the journal in the browser (as an app window
when Chrome, Edge or Brave is there, a tab otherwise), and stops when that
console window is closed. The records live in `Plainbook` in the home folder
unless `PLAINBOOK_ROOT` says otherwise; a newer file finds them there, and the
same folder serves a source install later, the files are the same. A second
start while the journal runs does not start a second journal: it opens the
browser on the one that runs.

The first run: Windows SmartScreen (*More info*, *Run anyway*); macOS
*Privacy & Security*, *Open Anyway*, after unzipping; Linux `chmod +x` once.
The README, "Checking a downloaded file", says how the file is verified.

For autostart the file takes the place of `python3 -m plainbook.server` in the
recipes above, with `PLAINBOOK_OPEN=0` in the environment so that a login does
not open a browser: `ExecStart=%h/Applications/Plainbook-<version>-linux-x86_64`
and `Environment=PLAINBOOK_OPEN=0` in the unit; the path of the exe as the
target of the Windows shortcut (its console window stays open, that is the
running journal) with `PLAINBOOK_OPEN=0` as a user environment variable; the
path of the file in `ProgramArguments` of the LaunchAgent with the variable in
`EnvironmentVariables`.

## The check after installing (not optional)

1. The tests are green.
2. http://localhost:8778 opens, their account is there, and the balance on the
   front page equals their real balance.
3. After a reboot the server comes up by itself (if autostart was set up).
4. With you watching, they opened and closed a test trade with a screenshot
   pasted by Ctrl+V, that all of it worked, and that the files appeared under
   `journal/trades/`.
5. With you watching, they filled a daily card (**+ DRC**) and it opened again
   filled in after saving.

Pasting a screenshot is the one place where browser script does the work: if
something breaks, it usually breaks there. Check it by hand, because the tests go
around the browser on that path.

## Moving old trades in

Once the check is done, ask them one question: did they keep trades somewhere
before, in Notion, in a spreadsheet, in another app, and do they want that
history here, so the statistics count from the first day? "No" is a fine
answer, and the journal starts with what they enter from now on. "Yes" is the
job of `tools/import_csv.py`: they export the old journal as CSV, you map its
columns to the fields of a trade, the tool writes the trades the way the
interface would, and the balance is then reconciled with the broker on the
Accounts tab. Run `python3 tools/import_csv.py --help` for the columns it takes,
and mind the one difference from step 6 above: for an import, the start balance
of an account is the balance it had before the first old trade, not the balance
today, and the difference to today is written as a correction afterwards.

You need the header line of their table, nothing more. Do not read the rows,
and do not ask for them: the tool prints only counts and sums, and that is
what you check against the old journal.

### With a Notion connection

An agent that has Notion connected can take the trades straight from the
database, and that path brings what a CSV export cannot: the text of every
page and its pictures, tied to the right trade. It also means the agent reads
the records, so say that plainly before starting and go on only with their
consent; afterwards, never retell what was in a trade. The order that worked:

1. **The schema first.** Fetch the database and its properties. Every select
   property (account, direction, style, result, timeframe) stores an id per
   option: fetch the name of each id and write the table down, never guess a
   name from the id. Map the accounts to the ids of the journal's accounts,
   the results to Win, Lose and BE, the directions to long and short.
2. **All the rows.** Query the database to the last page and keep the rows
   as they came, in a working folder outside `journal/` and outside the code.
   The number of rows must equal the number of trades they see in Notion.
3. **The pages.** For every row fetch the page body: the idea, the
   conclusions. Download the pictures the moment a page is fetched, the file
   links Notion hands out expire within minutes. One file per page and one
   folder of pictures per page, named by the Notion id.
4. **A table for the tool.** Build one CSV from the rows: a column per field
   the tool takes, the page body in the idea and conclusions columns, the
   Notion id in the id column, the picture file names in a column and their
   folder as `--pictures-dir`. Then it is the same `tools/import_csv.py`, the
   dry run, the summary, the real run. Do not write the trade files yourself:
   the tool checks every row the way the interface does, and a second run
   skips what is already in.
5. **The check.** Counts and the sum of PnL per account against Notion, then
   trade by trade: if Notion kept an R for each trade, compare it with the R
   the journal computed. Every R off by the same factor means a wrong start
   balance; one R off means one row. Finish with the balance on the front page
   against the broker, corrected on the Accounts tab.
6. **The working folder** with the downloaded rows and pages is their records
   too. Keep it beside the data, never beside the code, or delete it once the
   check is done and they agree.

When you are done, read [CLAUDE.md](CLAUDE.md), the rules for living with the
journal afterwards.

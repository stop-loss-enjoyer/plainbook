# Security

Plainbook is a local program. The server listens on `127.0.0.1` only, has no
logins and no accounts, and sends nothing anywhere. Everything it knows is in
the journal folder on your own disk. That shapes what a security problem here
looks like.

## Supported versions

Only the latest release gets fixes. A fix ships as the next version, the same
way every other change does, so updating is the whole remedy.

## What counts

- **A web page reaching the journal.** Any way for a site open in your browser
  to read or change records through the local server: DNS rebinding, a forged
  form, a cross-origin request that gets through. The server checks the `Host`
  and `Origin` headers against its own address; a way around that check is
  exactly what this file is for.
- **Records leaving the machine.** Anything that sends data out, or a document
  made with the share button that still carries a balance, a size or money.
- **Files outside the journal.** A path, a name or an upload that makes the
  server read or write anywhere other than the journal folder.
- **Records being lost.** A form or an action that removes data instead of
  moving it to `.trash`.

## What does not count

- **Someone with access to your user account.** They can open the folder
  directly; the journal is plain text and pictures on purpose.
- **Exposing the port yourself.** Forwarding 8778 to a network, putting it
  behind a proxy or running the server for other people is outside what the
  program is built for. It has no authentication and is not meant to.

## Reporting a problem

Please do not open a public issue for a vulnerability. Use **Report a
vulnerability** on the Security tab of this repository instead; it opens a
private advisory that only the maintainer can see.

Include the version (it stands next to the name on every page), what you did
and what happened. Do not send real trades: a journal made with
`python3 tools/demo_journal.py <folder>` shows the same problem without
anyone's history in it.

You will get an answer within a week. Once a fix is released, the advisory is
published with credit to you, unless you would rather not be named.

import QtQuick
import Quickshell.Io
import qs.Commons
import qs.Ui

// Trading journal — a local server on :8778 (unit plainbook.service).
// A click of any button opens or hides the window with the same script the
// hotkey uses, so the two never drift apart.
//
// The button carries the number of OPEN positions: that is the only thing
// wanting attention right now. Zero positions — just the icon, no number.
//
// The server state is told by the SHAPE of the glyph rather than by colour:
// in monochrome themes an urgent colour is indistinguishable from the normal one.
//   ok   a book         — the server answers
//   down a broken link  — the server does not
// The glyphs are written as escapes: PUA characters are invisible in an
// editor and used to get lost while editing.
//
// NOTE: edits to this file only take effect after omarchy restart shell.
BarWidget {
  id: root
  moduleName: "trader.plainbook"

  property int openCount: 0
  property bool up: false
  property string checkedAt: ""

  readonly property string state: up ? "ok" : "down"

  function glyphFor(s) {
    if (s === "down") return ""     // nf-fa-chain-broken
    return ""                       // nf-fa-book
  }

  function refresh() {
    if (!poll.running) poll.running = true
  }

  function accept(raw) {
    checkedAt = Qt.formatTime(new Date(), "HH:mm")
    var out = String(raw).trim()
    // The answer may arrive truncated or as an error page: anything that is
    // not a whole number counts as DOWN, not as zero open positions.
    if (out === "" || out === "DOWN" || !/^\d+$/.test(out)) {
      up = false
      return
    }
    openCount = parseInt(out, 10)
    up = true
  }

  Process {
    id: poll
    // -m 4 keeps the process from hanging, -f drops the body on 4xx/5xx.
    command: ["bash", "-c", "curl -sf -m 4 http://127.0.0.1:8778/open-count || echo DOWN"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: root.accept(text)
    }
    onExited: function (exitCode) {
      if (exitCode !== 0) root.up = false
    }
  }

  Timer {
    interval: 60000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  readonly property string tip: {
    if (!up) return "Plainbook: server not responding · " + checkedAt
    if (openCount === 0) return "Plainbook · no open positions · " + checkedAt
    var word = openCount === 1 ? "position" : "positions"
    return "Plainbook · " + openCount + " open " + word + " · " + checkedAt
  }

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: root.glyphFor(root.state)
    foreground: root.state === "down"
      ? (root.bar ? root.bar.urgent : Color.urgent)
      : (root.bar ? root.bar.barForeground : Color.foreground)
    tooltipText: root.tip
    onPressed: function (mouseButton) {
      if (root.bar) root.bar.run("plainbook-toggle")
    }
  }

  // The open-position counter: a filled badge in the corner of the icon. The
  // fill is needed because a thin digit over a dark bar read badly, and the
  // background colour differs between themes — so it is taken from the bar.
  Rectangle {
    id: badge
    visible: root.up && root.openCount > 0
    anchors.right: button.right
    anchors.bottom: button.bottom
    anchors.rightMargin: 0
    anchors.bottomMargin: 2
    width: Math.max(number.implicitWidth + 6, height)
    height: Math.round(Style.font.body * 0.95)
    radius: height / 2
    color: root.bar ? root.bar.barForeground : Color.foreground

    Text {
      id: number
      anchors.centerIn: parent
      text: String(root.openCount)
      font.family: root.bar ? root.bar.fontFamily : Style.font.family
      font.pixelSize: Math.round(Style.font.body * 0.68)
      font.bold: true
      color: root.bar ? root.bar.background : Color.background
    }
  }
}

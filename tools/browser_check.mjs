// The forms of the journal driven in a real (headless) browser: the tests go
// around the page scripts, and this is the one check that runs them. Needs
// Chromium and Node 22 or newer, nothing else. Run it against a FRESH demo
// journal, never against the owner's:
//
//   python3 tools/demo_journal.py /tmp/pb-demo        # an empty folder: it refuses one with records
//   PLAINBOOK_ROOT=/tmp/pb-demo PLAINBOOK_PORT=8899 python3 -m plainbook.server &
//   node tools/browser_check.mjs http://127.0.0.1:8899
//
// A second argument names the browser profile folder (kept; without it a
// temporary one is made and removed when the run ends), a third a folder to
// keep the PNG of the card in (it is deleted otherwise). The browser takes a
// debugging port of its own choosing, so a second run does not meet the first.
//
// Every line printed "ok:" is a step that behaved; the run stops at the first
// that did not, and any error the page logged is printed at the end. The one
// 400 it logs on purpose is the playbook form refusing rules changed under a
// held version.
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import { crc32, deflateSync } from "node:zlib";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

const B = process.argv[2] || "http://127.0.0.1:8899";
// a profile that was not asked for is ours to remove, and it must not be one
// shared name in /tmp that a run left behind with its cookies and caches
const OWN_PROFILE = !process.argv[3];
const PROFILE = process.argv[3] || mkdtempSync(join(tmpdir(), "plainbook-browser-check-"));
// a kept profile still names the port of the last run until the browser rewrites it
rmSync(join(PROFILE, "DevToolsActivePort"), { force: true });
// port 0 lets the browser pick a free one and write the number into the profile;
// its own process group, so that the helper processes of the browser stop with it
const chrome = spawn("chromium", ["--headless=new", "--remote-debugging-port=0",
  "--no-first-run", "--no-default-browser-check", "--disable-gpu",
  `--user-data-dir=${PROFILE}`,
  "about:blank"], { stdio: "ignore", detached: true });
function stopChrome() {
  try { process.kill(-chrome.pid, "SIGTERM"); } catch { /* already gone */ }
}
function dropProfile() {
  if (!OWN_PROFILE) return;
  try { rmSync(PROFILE, { recursive: true, force: true }); } catch { /* retried by the caller */ }
}
process.on("exit", () => { stopChrome(); dropProfile(); });
process.on("SIGINT", () => process.exit(130));
process.on("SIGTERM", () => process.exit(143));
// the profile can be removed only once the browser has let go of it
async function finish(code) {
  stopChrome();
  if (chrome.exitCode === null) await Promise.race([once(chrome, "exit"), sleep(5000)]);
  for (let i = 0; i < 20 && OWN_PROFILE && existsSync(PROFILE); i++) {
    dropProfile();
    await sleep(250);
  }
  process.exit(code);
}

async function debugPort() {
  for (let i = 0; i < 50; i++) {
    try { return Number(readFileSync(join(PROFILE, "DevToolsActivePort"), "utf8").split("\n")[0]); }
    catch { await sleep(200); }
  }
  throw new Error("chromium did not come up");
}
const PORT = await debugPort();

async function json(path) {
  for (let i = 0; i < 50; i++) {
    try { return await (await fetch(`http://127.0.0.1:${PORT}${path}`)).json(); }
    catch { await sleep(200); }
  }
  throw new Error("chromium did not come up");
}
const targets = await json("/json");
const page = targets.find(t => t.type === "page");
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise(r => ws.onopen = r);
let id = 0; const waiting = new Map(); const events = [];
const errors = [];
let expect400 = false;                 // set right before the submit that is refused
ws.onmessage = e => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
  else if (m.method) {
    events.push(m);
    // a form left with words in it asks before the page goes; the check
    // leaves such forms on purpose, so it answers yes
    if (m.method === "Page.javascriptDialogOpening" && m.params.type === "beforeunload")
      ws.send(JSON.stringify({ id: ++id, method: "Page.handleJavaScriptDialog", params: { accept: true } }));
    if (m.method === "Runtime.exceptionThrown")
      errors.push("exception: " + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text));
    if (m.method === "Runtime.consoleAPICalled" && (m.params.type === "error" || m.params.type === "warning"))
      errors.push(m.params.type + ": " + m.params.args.map(a => a.value ?? a.description).join(" "));
    if (m.method === "Log.entryAdded" && m.params.entry.level === "error") {
      // the one 400 the run provokes on purpose (step 6) is not an error of the page
      const expected = expect400 && /status of 400/.test(m.params.entry.text)
        && (m.params.entry.url || "").endsWith("/edit");
      if (expected) expect400 = false;
      else errors.push("log: " + m.params.entry.text + " " + (m.params.entry.url || ""));
    }
  }
};
function send(method, params = {}) {
  return new Promise(res => { const n = ++id; waiting.set(n, res); ws.send(JSON.stringify({ id: n, method, params })); });
}
await send("Page.enable"); await send("Runtime.enable"); await send("Log.enable");

async function loaded() {
  // a page that never finishes loading must end the run, not hang it
  await new Promise((res, rej) => {
    const gave = setTimeout(() => {
      clearInterval(t);
      rej(new Error("the page did not finish loading in 20 seconds"));
    }, 20000);
    const t = setInterval(() => {
      const i = events.findIndex(m => m.method === "Page.loadEventFired");
      if (i >= 0) { events.splice(i, 1); clearInterval(t); clearTimeout(gave); res(); }
    }, 30);
  });
  await sleep(120);
}
const api = {
  async goto(url) { events.length = 0; await send("Page.navigate", { url }); await loaded(); },
  async evaluate(expr) {
    const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.result.exceptionDetails) throw new Error("evaluate failed: " + JSON.stringify(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text) + " in " + expr.slice(0, 80));
    return r.result.result.value;
  },
  // submit a form and wait for the page that comes after; the header holds
  // the form of the Lite switch, so the first form is the page's own after it
  async submit(selector = "form:not(.lite-switch)") {
    events.length = 0;
    await send("Runtime.evaluate", { expression: `document.querySelector(${JSON.stringify(selector)}).requestSubmit()` });
    await loaded();
  },
  url() { return api.evaluate("location.pathname + location.search"); },
  errors,
};
const check = (cond, what) => { if (!cond) throw new Error("check failed: " + what); console.log("ok: " + what); };
// The day this run happens on. The trade below is opened and closed inside it,
// and the card is written for it. Written as a fixed date once, the check went
// red the morning after: the exit was earlier than the entry, which the journal
// refuses, and rightly.
const now = new Date();
const DAY = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, "0"),
             String(now.getDate()).padStart(2, "0")].join("-");

async function run(p) {
  const has = async (expr, word) => (await p.evaluate(expr)).toLowerCase().includes(word.toLowerCase());
  // ---- 1. write a playbook through the form, with the scripted parts
  await p.goto(B + "/playbook/new");
  await p.evaluate(`document.querySelector('[name=name]').value = 'Break test'`);
  await p.evaluate(`document.querySelector('[name=version]').value = '1.0'`);
  await p.evaluate(`document.querySelector('[name=block]').value = '2'`);
  await p.evaluate(`document.querySelector('[name=styles][value=swing]').checked = true`);
  await p.evaluate(`document.querySelector('[name=setup_name_1]').value = 'A'`);
  // a rule, Enter adds the next one under it
  await p.evaluate(`var t = document.querySelector('[name=setup_rule_1]'); t.value = 'Level marked'; t.dispatchEvent(new Event('input', {bubbles:true}));
    t.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true, cancelable:true}))`);
  check(await p.evaluate(`document.querySelectorAll('[name=setup_rule_1]').length`) === 2, "Enter added a second rule row");
  await p.evaluate(`document.querySelectorAll('[name=setup_rule_1]')[1].value = 'Target 2R'`);
  await p.evaluate(`document.querySelectorAll('[name=setup_rule_1_detail]')[1].value = 'the whole rule'`);
  // numbers run through the form
  check(await p.evaluate(`[...document.querySelectorAll('.rule-row .n')].map(e=>e.textContent).join(',')`) === "1,2,3,4", "rule numbers renumbered through setups, filters, management");
  // + setup
  await p.evaluate(`add_setup()`);
  check(await p.evaluate(`!!document.querySelector('[name=setup_name_2]')`), "+ setup added a second setup block");
  await p.evaluate(`document.querySelector('[name=setup_name_2]').value = 'B'; document.querySelector('[name=setup_rule_2]').value = 'Trend on D1'`);
  // remove a rule with the cross, at least one row stays
  await p.evaluate(`document.querySelector('[data-name=filter] .x').click()`);
  check(await p.evaluate(`document.querySelectorAll('[name=filter]').length`) === 1, "dropping the only filter row leaves one empty row");
  await p.evaluate(`document.querySelector('[name=filter]').value = 'News an hour away'`);
  await p.evaluate(`document.querySelector('[name=management]').value = 'Stop not moved'`);
  // limits: a known kind, and other with a name
  await p.evaluate(`add_limit(); add_limit()`);
  await p.evaluate(`var rows = document.querySelectorAll('.limit-row'); rows[0].querySelector('select').value='risk'; rows[0].querySelector('[name=limit_value]').value='1';
    var sel = rows[1].querySelector('select'); sel.value='other'; sel.dispatchEvent(new Event('change', {bubbles:true}));`);
  check(await p.evaluate(`!document.querySelectorAll('.limit-row')[1].querySelector('[name=limit_name]').hidden`), "choosing other shows the name field");
  await p.evaluate(`var r = document.querySelectorAll('.limit-row')[1]; r.querySelector('[name=limit_name]').value='per move'; r.querySelector('[name=limit_value]').value='5'`);
  await p.evaluate(`document.querySelector('[name=notes]').value = '## Math\\n\\nsome math'`);
  await p.submit();
  const pbUrl = await p.url();
  check(pbUrl.startsWith("/playbook/break-test"), "playbook written and landed on its page: " + pbUrl);
  const text = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  for (const w of ["Level marked", "Target 2R", "the whole rule", "Trend on D1", "News an hour away", "Stop not moved", "risk per trade", "per move", "some math", "block 1: 0 / 2"])
    check(text.includes(w.toLowerCase()), "page shows: " + w);
  check(await p.evaluate(`[...document.querySelectorAll('.rules .n')].map(e=>e.textContent).join(',')`) === "1,2,3,4,5", "page numbers 1..5");

  // ---- 2. open a trade under it: the checklist follows the select
  await p.goto(B + "/new");
  check(await p.evaluate(`document.getElementById('checklist-card').hidden`), "checklist hidden with no playbook");
  await p.evaluate(`var s=document.querySelector('[name=playbook]'); s.value='break-test'; s.dispatchEvent(new Event('change',{bubbles:true}))`);
  check(!(await p.evaluate(`document.getElementById('checklist-card').hidden`)), "checklist shown after picking the playbook");
  check(await p.evaluate(`document.querySelector('[name=style]').value`) === "swing", "style set from the playbook");
  check(await p.evaluate(`document.querySelector('.checklist:not([hidden]) .frame') !== null`), "frame drawn (the playbook has a risk limit)");
  check(await has(`document.querySelector('.checklist:not([hidden]) .tally').textContent`, "0 of 3"), "tally counts setup A rules + filter: 0 of 3");
  // switch to setup B: only its rules show
  await p.evaluate(`var r=document.querySelector('[name="setup_break-test"][value=B]'); r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true}))`);
  check(await has(`document.querySelector('.checklist:not([hidden]) .tally').textContent`, "0 of 2"), "setup B: 0 of 2");
  await p.evaluate(`var r=document.querySelector('[name="setup_break-test"][value=A]'); r.checked=true; r.dispatchEvent(new Event('change',{bubbles:true}))`);
  // tick rule 1, leave 2 and 4 with a why
  await p.evaluate(`var b=document.getElementById('met-break-test-1'); b.checked=true; b.dispatchEvent(new Event('change',{bubbles:true}))`);
  check(await p.evaluate(`document.getElementById('ticked').value`) === "1", "touching the checklist marks it ticked");
  check(await p.evaluate(`document.querySelector('[name=why_break-test_1]').hidden`), "why line hidden under a ticked rule");
  check(!(await p.evaluate(`document.querySelector('[name=why_break-test_2]').hidden`)), "why line shown under an empty rule");
  await p.evaluate(`document.querySelector('[name=why_break-test_2]').value='took 1.6R'`);
  check(await has(`document.querySelector('.checklist:not([hidden]) .tally').textContent`, "1 of 3"), "tally 1 of 3");
  // the risk figure in the frame follows the field
  await p.evaluate(`var r=document.querySelector('[name=risk]'); r.value='2'; r.dispatchEvent(new Event('input',{bubbles:true}))`);
  check(await p.evaluate(`document.querySelector('.checklist:not([hidden]) [data-risk]').classList.contains('over')`), "risk 2 over the cap of 1 turns red");
  await p.evaluate(`var r=document.querySelector('[name=risk]'); r.value='1'; r.dispatchEvent(new Event('input',{bubbles:true}))`);
  // the field takes money too: the line under it says the percent, and the
  // frame compares that percent to the cap
  // the form carries the history of every account, and the balance is the
  // one at the entry typed in the form
  const balance = await p.evaluate(`balance_of(document.querySelector('[name=account]').value)`);
  check(balance > 0, "the form works out the balance of the account at the entry: " + balance);
  check(await has(`document.querySelector('.field .risk-hint').textContent`, "= "), "a percent is said in money under the field");
  await p.evaluate(`var r=document.querySelector('[name=risk]'); r.value=${JSON.stringify(balance * 0.02 + "$")}; r.dispatchEvent(new Event('input',{bubbles:true}))`);
  check(await has(`document.querySelector('.field .risk-hint').textContent`, "= 2% of"), "money is said in percent under the field");
  check(await has(`document.querySelector('.checklist:not([hidden]) .risk-now').textContent`, "2%"), "the frame reads the percent of the money");
  check(await p.evaluate(`document.querySelector('.checklist:not([hidden]) [data-risk]').classList.contains('over')`), "money worth 2% over the cap of 1 turns red");
  await p.evaluate(`var r=document.querySelector('[name=risk]'); r.value='1'; r.dispatchEvent(new Event('input',{bubbles:true}))`);
  await p.evaluate(`document.querySelector('[name=pair]').value='EURUSD'; document.querySelector('[name=idea_text_1]').value='a test idea'`);
  await p.evaluate(`document.querySelector('[name=entry]').value=${JSON.stringify(DAY + "T09:00")}`);
  await p.submit();
  const tradeUrl = await p.url();
  check(tradeUrl.startsWith("/trade/"), "trade opened: " + tradeUrl);
  let page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("2 rules not met".toLowerCase()), "trade page: 2 rules not met");
  check(page.includes("took 1.6R".toLowerCase()), "trade page shows the why");
  check(page.includes("Ticked when the trade is closed".toLowerCase()), "management listed for the open trade");

  // ---- 2b. an update while it runs: the form on the trade page, its paste
  // zone made ready by the page script, the line under the trade after
  const tid = tradeUrl.split("/trade/")[1].split("?")[0];
  check(await p.evaluate(`!!document.querySelector('#updates form [name=update]')`), "open trade offers the update form");
  check(await p.evaluate(`document.querySelector('#updates .dropzone').dataset.ready === '1'`), "the update zone is ready for a paste");
  await p.evaluate(`document.querySelector('#updates [name=update]').value='stop moved under the low'`);
  await p.submit("#updates form");
  check((await p.url()).startsWith("/trade/" + tid), "the update lands back on the trade");
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("stop moved under the low"), "trade page shows the update");
  check(await p.evaluate(`document.querySelector('.toast').textContent`) === "Update added", "the page says Update added");

  // ---- 3. close it: the management checklist
  await p.goto(B + "/close/" + tid);
  check(await p.evaluate(`!!document.getElementById('exit-checklist')`), "close form has the management checklist");
  check(await has(`document.querySelector('#exit-checklist .tally').textContent`, "0 of 1"), "exit tally 0 of 1");
  check(!(await p.evaluate(`document.querySelector('[name=why_break-test_5]').hidden`)), "why shown under the unheld management rule");
  await p.evaluate(`document.querySelector('[name=why_break-test_5]').value='moved it at the news'`);
  await p.evaluate(`document.querySelector('[name=result]').value='Lose'; document.querySelector('[name=pnl]').value='-100'; document.querySelector('[name=exit]').value=${JSON.stringify(DAY + "T12:00")}`);
  await p.submit();
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("1 rule not held".toLowerCase()), "trade page: 1 rule not held");
  check(page.includes("moved it at the news".toLowerCase()), "exit why shown");

  // ---- 4. edit it without touching either checklist: nothing changes
  await p.goto(B + "/edit/" + tid);
  check(await p.evaluate(`document.getElementById('met-break-test-1').checked`), "edit form: rule 1 ticked as before");
  check(await p.evaluate(`document.querySelector('[name=why_break-test_2]').value`) === "took 1.6R", "edit form carries the why");
  await p.submit();
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("2 rules not met".toLowerCase()) && page.includes("1 rule not held".toLowerCase()) && page.includes("took 1.6R".toLowerCase()), "edit kept both checklists and the reasons");

  // ---- 5. the playbook page: figures, reasons, review, block due
  await p.goto(B + "/playbook/break-test");
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("What a rule costs".toLowerCase()), "rule cost table present");
  check(page.includes("Reasons given".toLowerCase()), "reasons folded on the page");
  check(page.includes("block 1: 1 / 2".toLowerCase()), "block count 1 / 2");
  await p.evaluate(`document.querySelector('[name=review]').value='block one reviewed'`);
  await p.submit("form[action$='/review']");
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("block one reviewed".toLowerCase()), "review entry added");
  // a second trade completes the block: the tab asks
  await p.goto(B + "/new");
  await p.evaluate(`var s=document.querySelector('[name=playbook]'); s.value='break-test'; s.dispatchEvent(new Event('change',{bubbles:true}))`);
  await p.evaluate(`document.querySelector('[name=pair]').value='GBPUSD'; document.querySelector('[name=idea_text_1]').value='second'`);
  await p.submit();
  await p.goto(B + "/");
  check(!(await p.evaluate(`document.querySelector('header nav a[href="/playbooks"]').classList.contains('attention')`)), "block 1 complete and reviewed: the tab is plain");
  for (const pair of ["USDJPY", "AUDUSD"]) {
    await p.goto(B + "/new");
    await p.evaluate(`var s=document.querySelector('[name=playbook]'); s.value='break-test'; s.dispatchEvent(new Event('change',{bubbles:true}))`);
    await p.evaluate(`document.querySelector('[name=pair]').value='${pair}'; document.querySelector('[name=idea_text_1]').value='more'`);
    await p.submit();
  }
  await p.goto(B + "/");
  check(await p.evaluate(`document.querySelector('header nav a[href="/playbooks"]').classList.contains('attention')`), "block 2 complete without a review: the tab is amber");
  await p.goto(B + "/playbooks");
  check(await has(`document.body.innerText`, "review due"), "list says review due");
  // ---- 6. revise the rules under the same number: refused with the form back
  await p.goto(B + "/playbook/break-test/edit");
  await p.evaluate(`document.querySelector('[name=setup_rule_1]').value='Level marked on W'`);
  expect400 = true;
  await p.submit();
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("Give the new rules a new number".toLowerCase()), "rules changed under a held version are refused");
  check(await p.evaluate(`document.querySelector('[name=setup_rule_1]').value`) === "Level marked on W", "the typed rule is kept in the form");
  await p.evaluate(`document.querySelector('[name=version]').value='1.1'`);
  await p.submit();
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("Earlier versions".toLowerCase()) && page.includes("1.0".toLowerCase()), "old version kept and listed");
  await p.goto(B + "/trade/" + tid);
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("Level marked".toLowerCase()) && !page.includes("Level marked on W".toLowerCase()), "the trade shows the rules of its own version 1.0");
  await p.goto(B + "/stats");
  page = (await p.evaluate(`document.body.innerText`)).toLowerCase();
  check(page.includes("By playbook".toLowerCase()) && page.includes("Break test".toLowerCase()), "statistics show the playbook");
  await p.goto(B + "/playbook/break-test/version/1.0");
  check((await p.evaluate(`document.body.innerText`)).toLowerCase().includes("kept"), "frozen version page opens");

  // ---- 7. the report card: the trades of the day offered to the two fields
  // that name a trade, the best one and the assessment
  await p.goto(B + "/card/" + DAY + "/edit");       // the day the trade above closed
  check(await p.evaluate(`!!document.querySelector('select.pick[data-into=best]')`),
    "the card offers the day's trades to the best trade");
  const label = await p.evaluate(`document.querySelector('select.pick option:nth-child(2)').value`);
  await p.evaluate(`var i=document.querySelector('.pick'); i.value=${JSON.stringify(label)}; i.dispatchEvent(new Event('change',{bubbles:true}))`);
  // the day may already have a card with words in it, so what is checked is
  // that the pick was inserted, not that it is the whole field
  check(await has(`document.querySelector('textarea[name=best]').value`, label),
    "picking a trade writes it into the best trade: " + label);
  check(await p.evaluate(`document.querySelector('.pick').value`) === "",
    "the picker goes back to empty, so it saves nothing of its own");
  // the day may already have a card with rows written by hand (the demo
  // journal writes one for today), and a result typed by a person is kept:
  // the check types into the first empty row
  const ROW = `[...document.querySelectorAll('table.assessment tr')].find(r => r.querySelector('[name=assess_trade]') && !r.querySelector('[name=assess_trade]').value)`;
  await p.evaluate(`var t=(${ROW}).querySelector('[name=assess_trade]'); t.value=${JSON.stringify(label)}; t.dispatchEvent(new Event('input',{bubbles:true}))`);
  check(await has(`(${ROW.replace("!r.querySelector('[name=assess_trade]').value", "r.querySelector('[name=assess_id]').value")}).querySelector('[name=assess_result]').value`, "lose"),
    "the assessment fills the result of the picked trade");
  const FILLED = `[...document.querySelectorAll('table.assessment tr')].find(r => r.querySelector('[name=assess_trade]') && r.querySelector('[name=assess_trade]').value === ${JSON.stringify(label)})`;
  check(await p.evaluate(`(${FILLED}).querySelector('[name=assess_id]').value`) !== "",
    "the row remembers which trade it names");
  await p.evaluate(`var t=(${FILLED}).querySelector('[name=assess_trade]'); t.value='a trade of my own'; t.dispatchEvent(new Event('input',{bubbles:true}))`);
  check(await p.evaluate(`[...document.querySelectorAll('[name=assess_trade]')].every(t => t.value !== 'a trade of my own' || t.closest('tr').querySelector('[name=assess_id]').value === '')`),
    "a text the journal does not know lets the trade go");
  await p.evaluate(`var t=[...document.querySelectorAll('[name=assess_trade]')].find(t => t.value === 'a trade of my own'); t.value=${JSON.stringify(label)}; t.dispatchEvent(new Event('input',{bubbles:true}))`);
  await p.evaluate(`document.querySelector('[name=grade]').value='B'`);
  await p.submit();
  check((await p.url()).startsWith("/card/" + DAY), "the card saved: " + (await p.url()));
  await p.goto(B + "/card/" + DAY + "/edit");        // a saved card opens to be read, its form is at /edit
  check(await has(`document.querySelector('textarea[name=best]').value`, label),
    "the card came back with the trade in the best trade");
  check(await p.evaluate(`[...document.querySelectorAll('select.pick option[class]')].some(o => o.textContent.includes(' · ') && o.className)`),
    "the picker says how each closed trade ended, in its colour");
  // lines of the assessment are added and taken away on the form
  const LINES = `document.querySelectorAll('table.assessment tbody tr').length`;
  const lines = await p.evaluate(LINES);
  await p.evaluate(`document.querySelector('.add-line').click()`);
  check(await p.evaluate(LINES) === lines + 1, "+ line adds a line to the assessment");
  check(await p.evaluate(`document.activeElement.name === 'assess_trade' && document.activeElement.value === '' && document.activeElement.closest('tr').querySelector('.n').textContent === '${lines + 1}.'`),
    "the new line is empty, numbered and has the cursor");
  await p.evaluate(`document.querySelector('table.assessment tbody tr:first-child .x').click()`);
  check(await p.evaluate(LINES) === lines
        && await p.evaluate(`document.querySelector('table.assessment tbody tr:first-child .n').textContent`) === "1.",
    "a line is removed and the rest renumbered");
  check(await p.evaluate(`document.activeElement.name === 'assess_trade'`),
    "and the cursor stays in the table");
  // a line added or taken away is a change to save: the card is saved, or
  // leaving it would rightly ask first
  await p.submit();
  check((await p.url()).startsWith("/card/" + DAY), "the card saved with its lines");

  // ---- 7b. a written card opens to be read: Edit leads to the form, Save
  // comes back to the reading
  await p.goto(B + "/card/" + DAY);
  check(await p.evaluate(`!!document.querySelector('.read-text') && !document.querySelector('textarea')`),
    "a written card opens to be read, with no form");
  check(await p.evaluate(`!!document.querySelector('header .right a.btn[href="/card/${DAY}/edit"]')`),
    "the read view has Edit at the top right");
  events.length = 0;
  await p.evaluate(`document.querySelector('header .right a.btn[href$="/edit"]').click()`);
  await loaded();
  check((await p.url()) === "/card/" + DAY + "/edit"
        && await p.evaluate(`!!document.querySelector('textarea[name=overview]')`),
    "Edit opens the form of the card");
  const EDITED = "read mode check " + Date.now();
  await p.evaluate(`document.querySelector('textarea[name=overview]').value=${JSON.stringify(EDITED)}`);
  await p.submit();
  check((await p.url()).split("?")[0] === "/card/" + DAY
        && await has(`document.querySelector('.wrap').innerText`, EDITED),
    "Save lands on the read view with the new text");
  check(await p.evaluate(`!document.querySelector('textarea')`), "and it is still no form");

  // ---- the Download button of a preview, the one place a page fetches a
  // file for itself. The anchor click is caught, so a checking run saves
  // nothing to disk.
  await p.goto(B + "/share/journal?shots=0");
  check(await p.evaluate(`!!document.querySelector('.bar a.primary')`),
    "the preview carries the Download button");
  await p.evaluate(`window.__saved = null;
    HTMLAnchorElement.prototype.click = function(){
      window.__saved = {name: this.download, href: this.href}; };`);
  const saving = await p.evaluate(`(async () => {
    const link = document.querySelector('.bar a.primary');
    const done = share_save(link);
    const during = link.textContent;
    const busy = link.classList.contains('busy');
    await done;
    return [during, busy, link.textContent,
            window.__saved && window.__saved.name,
            window.__saved && window.__saved.href.slice(0, 5)].join("|");
  })()`);
  const [during, busy, after, name, kind] = saving.split("|");
  check(during.startsWith("Building the file"), "the button says it is building: " + during);
  check(busy === "true", "the button is marked busy while it builds");
  check(after === "Saved", "the button says the file was saved");
  check(name.startsWith("plainbook-trades-") && name.endsWith(".html"),
    "the file is handed over named: " + name);
  check(kind === "blob:", "the page saves a file it built itself");

  // ---- the paste path: two pictures pasted at once into an idea block,
  // and Save pressed before they are up. The save waits for both, and the
  // trade comes out with both, under two names.
  await p.goto(B + "/new");
  await p.evaluate(`document.querySelector('[name=pair]').value='GBPUSD';
    document.querySelector('[name=style]').value='swing';
    document.querySelector('[name=idea_text_1]').value='two pictures at once';
    document.querySelector('[name=entry]').value=${JSON.stringify(DAY + "T08:00")}`);
  events.length = 0;
  await p.evaluate(`(async () => {
    // a one-pixel PNG drawn by the page itself
    const c = document.createElement('canvas'); c.width = c.height = 1;
    const png = await new Promise(r => c.toBlob(r, 'image/png'));
    const dt = new DataTransfer();
    dt.items.add(new File([png], 'a.png', {type: 'image/png'}));
    dt.items.add(new File([png], 'b.png', {type: 'image/png'}));
    const zone = document.querySelector('.dropzone[data-zone="idea-1"]');
    zone.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true}));
    document.querySelector('form:not(.lite-switch)').requestSubmit();
  })()`);
  await loaded();
  check((await p.url()).startsWith("/trade/"), "the save went out once the pictures were up");
  const shots = await p.evaluate(`[...document.querySelectorAll('img[alt="idea screenshot"]')].map(i => i.src.split('/').pop()).join(' ')`);
  check(shots.split(" ").length === 2 && new Set(shots.split(" ")).size === 2,
    "both pasted pictures reached the trade: " + shots);

  // ---- a screenshot opens over the page, and Esc closes it
  await p.evaluate(`document.querySelector('.shots img').click()`);
  check(await p.evaluate(`!!document.querySelector('.viewer img')`), "a screenshot opens over the page");
  await p.evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))`);
  check(await p.evaluate(`!document.querySelector('.viewer')`), "Esc closes it");

  // ---- Accounts: two timeframes ticked go with one button, and the page
  // comes back on the same list, open, instead of at the top with it shut
  await p.goto(B + "/accounts");
  for (const w of ["T1", "T2"]) {
    await p.evaluate(`document.querySelector('#list-timeframes [name=word][type=text]').value = '${w}'`);
    await p.submit("#list-timeframes form.filters");
  }
  check((await p.url()).includes("at=list-timeframes"), "adding a word comes back to its list");
  await p.evaluate(`['T1', 'T2'].forEach(w => document.querySelector('input[type=checkbox][form=drop-timeframes][value=' + w + ']').checked = true)`);
  await p.submit("#drop-timeframes");
  check(!(await has(`document.querySelector('#list-timeframes table').innerText`, "T1"))
        && !(await has(`document.querySelector('#list-timeframes table').innerText`, "T2")),
    "Remove selected took both ticked timeframes");
  check(await p.evaluate(`document.getElementById('list-timeframes').open`), "the list is open after it");
  // below the sticky header, which is taller once its tabs wrap
  check(await p.evaluate(`(() => { const r = document.getElementById('list-timeframes').getBoundingClientRect();
    const head = document.querySelector('header').getBoundingClientRect().bottom;
    return scrollY > 0 && r.top >= head && r.top < innerHeight; })()`), "and the page stands on it");
  await send("Emulation.setDeviceMetricsOverride", { width: 600, height: 900, deviceScaleFactor: 1, mobile: false });
  await p.goto(B + "/accounts?at=pairs");
  check(await p.evaluate(`(() => { const r = document.getElementById('pairs').getBoundingClientRect();
    return scrollY > 0 && r.top >= document.querySelector('header').getBoundingClientRect().bottom; })()`),
    "a narrow window with a wrapped header lands on the part below the header");
  // ---- Statistics: the stop edge slider comes back on its card, not at the top
  await p.goto(B + "/stats");
  events.length = 0;
  await p.evaluate(`(() => { const r = document.querySelector('#past-stop input[type=range]');
    r.value = '1.5'; r.dispatchEvent(new Event('change', {bubbles: true})); })()`);
  await loaded();
  check(await p.evaluate(`location.hash`) === "#past-stop", "the slider comes back to its card");
  check(await p.evaluate(`(() => { const r = document.getElementById('past-stop').getBoundingClientRect();
    return scrollY > 0 && r.top >= document.querySelector('header').getBoundingClientRect().bottom && r.top < innerHeight; })()`),
    "and the page stands on it, below the wrapped header");
  check(await p.evaluate(`document.querySelector('#past-stop output').textContent`) === "-1.5 R", "with the new edge");
  await send("Emulation.clearDeviceMetricsOverride");

  // ---- the Cards tab is one screen in any window: the calendar of the
  // quarter takes the height there is, the page never scrolls, and no square
  // shows a line cut through
  for (const [width, height] of [[800, 600], [1280, 720], [1440, 900], [1920, 1080], [3840, 2160]]) {
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
    await p.goto(B + "/cards");
    check(await p.evaluate(`(() => {
      const d = document.documentElement;
      const cells = [...document.querySelectorAll('.cal-day, .cal-week')];
      const cut = cells.some(c => [...c.children].some(k => getComputedStyle(k).display !== 'none'
        && k.getBoundingClientRect().bottom > c.getBoundingClientRect().bottom - 1));
      return cells.length > 0 && d.scrollHeight <= innerHeight && d.scrollWidth <= innerWidth && !cut;
    })()`), `the Cards tab fits ${width}x${height} without a scroll or a cut line`);
  }
  await send("Emulation.clearDeviceMetricsOverride");

  // ---- the plan menu follows the date of the entry: today it offers the
  // plans that cover today, a date inside an older plan offers that one, and
  // a day no plan covers says so
  await p.goto(B + "/new");
  const menu = () => p.evaluate(`[...document.querySelector('select[name=plan]').options].map(o => o.value + '|' + o.textContent)`);
  const enter = day => p.evaluate(`(() => { const e = document.querySelector('[name=entry]');
    e.value = ${JSON.stringify(day + "T10:00")}; e.dispatchEvent(new Event('change', {bubbles: true})); })()`);
  let offeredNow = (await menu()).map(o => o.split("|")[0]).filter(Boolean);
  const plans = JSON.parse(await p.evaluate(`document.querySelector('select[name=plan]').dataset.plans`));
  // the demo plans run Monday to Friday, so on a weekend no plan covers today
  // and the run starts from the last day of the newest plan instead
  let from = DAY;
  if (!offeredNow.length && plans.length) {
    from = plans.reduce((a, b) => (a.to > b.to ? a : b)).to;
    await enter(from);
    offeredNow = (await menu()).map(o => o.split("|")[0]).filter(Boolean);
  }
  const older = plans.find(k => k.to < from && !offeredNow.includes(k.id));
  check(offeredNow.length > 0 && older, "the menu offers today's plans and the page knows an older one");
  await enter(older.to);
  const back = (await menu()).map(o => o.split("|")[0]).filter(Boolean);
  check(back.includes(older.id) && offeredNow.every(id => !back.includes(id)),
    "a date inside an older plan offers it and drops today's");
  await p.evaluate(`document.querySelector('select[name=plan]').value = ${JSON.stringify(older.id)}`);
  await enter("2001-01-02");
  const none = await menu();
  check(none.length === 1 && none[0] === "|no plan covers this day" &&
    await p.evaluate(`document.querySelector('select[name=plan]').value`) === "",
    "a day no plan covers says so and drops the pick");
  // a trade being edited keeps its own plan whatever date it is moved to,
  // or a save would untie it from the plan
  await p.goto(B + "/plan/" + encodeURIComponent(older.id));
  const tied = await p.evaluate(`(document.querySelector('a[href^="/trade/"]') || {}).getAttribute?.('href')`);
  check(tied, "the older plan has a trade tied to it");
  await p.goto(B + "/edit/" + tied.split("/")[2].split("?")[0]);
  check(await p.evaluate(`document.querySelector('select[name=plan]').value`) === older.id,
    "the edit form of that trade has its plan picked");
  await enter("2001-01-02");
  check(await p.evaluate(`document.querySelector('select[name=plan]').value`) === older.id,
    "and keeps it when the date moves to a day no plan covers");

  // ---- the Plans tab keeps the current plans apart from the past ones
  await p.goto(B + "/plans");
  check(await p.evaluate(`[...document.querySelectorAll('.card h2')].map(h => h.textContent).join(',')`) === "Current,Past",
    "the Plans tab has a Current table and a Past table");
  await send("Emulation.setDeviceMetricsOverride", { width: 900, height: 900, deviceScaleFactor: 1, mobile: false });
  check(await p.evaluate(`getComputedStyle(document.querySelector('th.hide-narrow')).display`) === "none",
    "a narrow window hides WR, PnL and the narrative column of Past");
  await send("Emulation.clearDeviceMetricsOverride");

  // ---- the Notes tab is tiles; a pinned note comes first
  await p.goto(B + "/notes");
  const tiles = () => p.evaluate(`[...document.querySelectorAll('.note-grid > a.note-tile')].map(a => a.getAttribute('href') + '|' + a.querySelector('.note-title').textContent)`);
  const listed = await tiles();
  check(listed.length >= 3 && await p.evaluate(`!document.querySelector('.card table')`),
    "the Notes tab draws tiles, not a table");
  check(await p.evaluate(`[...document.querySelectorAll('.note-pic img')].every(i => i.loading === 'lazy' && getComputedStyle(i).objectFit === 'contain')`),
    "a picture is shown whole and loaded lazily");
  const href = word => listed.find(t => t.includes(word)).split("|")[0];
  // the demo ships one pinned note; unpin it, then pin another and see it first
  await p.goto(B + href("swing plan"));
  await p.submit('form[action$="/unpin"]');
  await p.goto(B + href("Friday"));
  await p.submit('form[action$="/pin"]');
  await p.goto(B + "/notes");
  const pinnedFirst = await tiles();
  check(pinnedFirst[0].includes("Friday") && await p.evaluate(`!!document.querySelector('.note-tile .chip')`),
    "a pinned note is the first tile and wears the mark");
  // narrow window: the grid falls to one column by itself
  await send("Emulation.setDeviceMetricsOverride", { width: 420, height: 900, deviceScaleFactor: 1, mobile: false });
  check(await p.evaluate(`new Set([...document.querySelectorAll('.note-grid > a')].map(a => Math.round(a.getBoundingClientRect().left))).size`) === 1,
    "a narrow window gives one column of tiles");
  await send("Emulation.clearDeviceMetricsOverride");
  // the outdated ones are folded below
  await p.goto(B + href("Round numbers"));
  check(await has(`document.body.innerText`, "Marked outdated on"), "an outdated note says since when");
  await p.goto(B + "/notes");
  check(await p.evaluate(`!!document.querySelector('details.fold .note-tile.outdated') && !document.querySelector('details.fold').open`),
    "outdated notes sit in a closed fold");


  // ---- the catalogue on Accounts: ticked instruments join the list of pairs
  await p.goto(B + "/accounts?at=pair-catalogue");
  await p.evaluate(`for (const v of ['SOLUSD', 'USDTRY'])
    document.querySelector('#pair-catalogue [name=pair][value=' + v + ']').checked = true`);
  await p.submit("#pair-catalogue form");
  check(await p.evaluate(`!!document.querySelector('#pair-catalogue [value=SOLUSD][checked][disabled]')`),
    "a ticked instrument of the catalogue joined the list");

  // ---- the backup: downloaded, chosen in the form as a file, restored. The
  // browser writes the form itself, which is the part the tests cannot do
  await p.goto(B + "/accounts");
  const size = await p.evaluate(`(async () => {
    const blob = await (await fetch('/backup.plainbook')).blob();
    const dt = new DataTransfer();
    dt.items.add(new File([blob], 'Plainbook.plainbook'));
    document.querySelector('#backup [name=backup]').files = dt.files;
    return blob.size;
  })()`);
  check(size > 1000, "the backup downloads: " + size + " bytes");
  await p.submit("#backup form[action='/backup/upload']");
  check((await p.url()).startsWith("/restore/"), "the chosen file leads to its restore page");
  check(await has(`document.body.innerText`, "Restore this journal"), "the restore page offers to take it");
  await p.submit("form[action^='/restore/']:not([action$='/cancel'])");
  check((await p.url()).startsWith("/"), "restored and back on the journal");
  await p.goto(B + "/accounts");
  check(await p.evaluate(`!!document.querySelector('#backup form[action="/backup/put-back"]')`),
    "the journal it replaced can be put back");

  // ---- a picture dropped from a folder lands like a pasted one, and the
  // zone offers a button to choose a file
  await p.goto(B + "/new");
  check(await p.evaluate(`!!document.querySelector('.dropzone[data-zone="idea-1"] .pick')`),
    "the zone offers Choose a file");
  const dropped = await p.evaluate(`(async () => {
    const c = document.createElement('canvas'); c.width = c.height = 1;
    const png = await new Promise(r => c.toBlob(r, 'image/png'));
    const dt = new DataTransfer();
    dt.items.add(new File([png], 'dragged.png', {type: 'image/png'}));
    const zone = document.querySelector('.dropzone[data-zone="idea-1"]');
    zone.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    for (let i = 0; i < 50 && !zone.querySelector('.shot'); i++)
      await new Promise(r => setTimeout(r, 50));
    return zone.querySelectorAll('.shot').length;
  })()`);
  check(dropped === 1, "a dropped picture lands in the zone");

  // ---- screenshots: reordered by dragging, put back after the cross, and
  // drawn side by side on the trade page. The pictures are told apart by their
  // width, which is a mark that survives the save.
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  const WIDTHS = `[...document.querySelectorAll('.dropzone[data-zone="idea-1"] .shot img')].map(i => i.naturalWidth).join()`;
  const SAVED = `[...document.querySelectorAll('img[alt="idea screenshot"]')].map(i => i.naturalWidth).join()`;
  const paste = (zone, widths) => p.evaluate(`(async () => {
    const dt = new DataTransfer();
    for (const w of ${JSON.stringify(widths)}) {
      const c = document.createElement('canvas'); c.width = w; c.height = 100;
      c.getContext('2d').fillRect(0, 0, w, 100);
      dt.items.add(new File([await new Promise(r => c.toBlob(r, 'image/png'))], w + '.png', {type: 'image/png'}));
    }
    const zone = document.querySelector('.dropzone[data-zone="${zone}"]');
    const had = zone.querySelectorAll('.shot').length;
    zone.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true}));
    for (let i = 0; i < 100 && zone.querySelectorAll('.shot').length < had + ${widths.length}; i++)
      await new Promise(r => setTimeout(r, 50));
    for (const img of zone.querySelectorAll('.shot img'))
      if (!img.complete) await new Promise(r => img.addEventListener('load', r));
    return zone.querySelectorAll('.shot').length;
  })()`);
  // a thumbnail dragged onto the left half of another, or past the last one
  const drag = (from, to) => p.evaluate(`(() => {
    const zone = document.querySelector('.dropzone[data-zone="idea-1"]');
    const shots = [...zone.querySelectorAll('.shot')];
    const at = ${to} < shots.length ? shots[${to}].getBoundingClientRect() : null;
    const last = shots[shots.length - 1].getBoundingClientRect();
    const spot = at ? {clientX: at.left + 3, clientY: at.top + at.height / 2}
                    : {clientX: last.right - 3, clientY: last.top + last.height / 2};
    const dt = new DataTransfer();
    const fire = (el, type) => el.dispatchEvent(new DragEvent(type,
      {bubbles: true, cancelable: true, dataTransfer: dt, ...spot}));
    fire(shots[${from}].querySelector('img'), 'dragstart');
    fire(at ? shots[${to}] : zone, 'dragover');
    const marked = !!zone.querySelector('.drop-before, .drop-after');
    fire(at ? shots[${to}] : zone, 'drop');
    fire(shots[${from}].querySelector('img'), 'dragend');
    return marked && !zone.querySelector('.dragging, .drop-before, .drop-after');
  })()`);
  // the form above is left with a picture in it on purpose, and a browser does
  // not ask about a page nobody clicked in: say it is saved so it leaves quietly
  await p.evaluate(`unsaved = null`);
  await p.goto(B + "/new");
  await p.evaluate(`document.querySelector('[name=pair]').value='NZDUSD';
    document.querySelector('[name=style]').value='swing';
    document.querySelector('[name=idea_text_1]').value='three charts';
    document.querySelector('[name=entry]').value=${JSON.stringify(DAY + "T07:00")}`);
  check(await paste("idea-1", [1600, 1500, 1400]) === 3, "three pictures pasted into the idea block");
  check(await p.evaluate(WIDTHS) === "1600,1500,1400", "they stand in the order they were pasted");
  check(await drag(2, 0), "a drag shows where the picture lands and leaves no mark behind");
  check(await p.evaluate(WIDTHS) === "1400,1600,1500", "the last picture dragged before the first");
  check(await p.evaluate(`document.querySelector('.dropzone[data-zone="idea-1"] .shot input[name^=order_]') !== null`),
    "every picture carries its place in the order");
  await p.submit();
  const dragged = (await p.url()).split("?")[0];
  check(dragged.startsWith("/trade/"), "the trade with the reordered pictures is saved");
  check(await p.evaluate(SAVED) === "1400,1600,1500", "the page shows the pictures in the dragged order");
  // two pictures of a block sit side by side, none wider than half the card
  const row = await p.evaluate(`(() => {
    const [a, b] = [...document.querySelectorAll('.idea-block .shots img')].map(i => i.getBoundingClientRect());
    const card = document.querySelector('.idea-block').getBoundingClientRect();
    return [Math.abs(a.top - b.top) < 2, b.left >= a.right, a.width <= card.width / 2 + 1,
            a.width > 300 && a.width <= 481].join();
  })()`);
  check(row === "true,true,true,true", "two idea screenshots sit side by side, each at most half the card and 480 wide: " + row);
  // narrower, where half the card is less than the cap and is the limit
  await send("Emulation.setDeviceMetricsOverride", { width: 860, height: 900, deviceScaleFactor: 1, mobile: false });
  check(await p.evaluate(`(() => { const i = document.querySelector('.idea-block .shots img').getBoundingClientRect();
    const card = document.querySelector('.idea-block').getBoundingClientRect();
    return card.width < 960 && i.width <= card.width / 2 + 1 && i.width > card.width / 2 - 40; })()`),
    "in a middle window a picture takes half the card");
  await send("Emulation.setDeviceMetricsOverride", { width: 600, height: 900, deviceScaleFactor: 1, mobile: false });
  check(await p.evaluate(`(() => { const i = document.querySelector('.idea-block .shots img');
    return i.getBoundingClientRect().width > document.querySelector('.idea-block').getBoundingClientRect().width * 0.8; })()`),
    "a narrow window gives a picture the whole width");
  await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 1, mobile: false });
  await p.evaluate(`document.querySelector('.idea-block .shots img').click()`);
  check(await p.evaluate(`!!document.querySelector('.viewer img')`), "a click on a half-width picture opens the viewer");
  await p.evaluate(`document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}))`);

  // a new picture pasted into a saved block, dragged between two kept ones
  await p.goto(B + "/edit/" + dragged.split("/")[2]);
  check(await paste("idea-1", [1300]) === 4, "a fourth picture pasted into the saved block");
  check(await drag(3, 1), "and dragged between two of the old ones");
  check(await p.evaluate(WIDTHS) === "1400,1300,1600,1500", "it stands between them in the form");
  await p.submit();
  check(await p.evaluate(SAVED) === "1400,1300,1600,1500", "kept and new pictures are saved in the order seen");

  // the cross, then Undo, in the same place and still saved
  await p.goto(B + "/edit/" + dragged.split("/")[2]);
  const ZONE = `document.querySelector('.dropzone[data-zone="idea-1"]')`;
  check(await p.evaluate(`unsaved === null`), "a form just opened is not marked unsaved");
  await p.evaluate(`${ZONE}.querySelectorAll('.shot .remove')[1].click()`);
  check(await p.evaluate(`unsaved !== null`), "taking a picture off marks the form unsaved");
  check(await p.evaluate(`${ZONE}.querySelectorAll('.shot').length`) === 3
        && await has(`${ZONE}.querySelector('.hint').textContent`, "Screenshot removed")
        && await p.evaluate(`!!${ZONE}.querySelector('.hint .undo')`),
    "the cross removes the picture and the hint offers Undo");
  await p.evaluate(`${ZONE}.querySelector('.hint .undo').click()`);
  check(await p.evaluate(WIDTHS) === "1400,1300,1600,1500"
        && !(await has(`${ZONE}.querySelector('.hint').textContent`, "removed")),
    "Undo puts the same picture back in its place and the hint is plain again");
  check(await p.evaluate(`unsaved === null`), "Undo with nothing else changed leaves the form unmarked");
  await p.evaluate(`${ZONE}.querySelectorAll('.shot .remove')[1].click()`);
  await p.evaluate(`(t => { t.value += ' '; t.dispatchEvent(new Event('input', {bubbles: true})); })(document.querySelector('[name="idea_text_1"]'))`);
  await p.evaluate(`${ZONE}.querySelector('.hint .undo').click()`);
  check(await p.evaluate(`unsaved !== null`), "Undo after typing keeps the form marked");
  await p.evaluate(`unsaved = null`);       // the space typed above is not wanted
  await p.goto(B + "/edit/" + dragged.split("/")[2]);
  await p.evaluate(`${ZONE}.querySelectorAll('.shot .remove')[1].click()`);
  await p.evaluate(`${ZONE}.querySelector('.hint .undo').click()`);
  await p.submit();
  check(await p.evaluate(SAVED) === "1400,1300,1600,1500", "a picture removed and put back is still saved");
  await p.goto(B + "/edit/" + dragged.split("/")[2]);
  await p.evaluate(`${ZONE}.querySelector('.shot .remove').click()`);
  check(await paste("idea-1", [1200]) === 4 && !(await has(`${ZONE}.querySelector('.hint').textContent`, "removed")),
    "a new paste takes the Undo offer away");
  await p.evaluate(`${ZONE}.querySelectorAll('.shot .remove')[1].click()`);
  await sleep(8400);
  check(await p.evaluate(`!${ZONE}.querySelector('.hint .undo')`), "the Undo offer goes after a few seconds");

  // the review of a playbook is edited in its own form, which once had a zone
  // that drew the pictures and did nothing else
  await p.evaluate(`unsaved = null`);       // the trade form above is left on purpose
  await p.goto(B + "/playbook/break-test/edit");
  check(await paste("review", [900]) === 1, "a picture pasted into the review of a playbook");
  await p.submit();
  const REVIEW = `document.querySelectorAll('img[src*="/playbook-shot/"]').length`;
  check(await p.evaluate(REVIEW) === 1, "the playbook page shows the pasted review picture");
  await p.goto(B + "/playbook/break-test/edit");
  await p.evaluate(`document.querySelector('.dropzone[data-zone="review"] .shot .remove').click()`);
  check(await p.evaluate(`document.querySelectorAll('.dropzone[data-zone="review"] .shot').length`) === 0
        && await p.evaluate(`!!document.querySelector('.dropzone[data-zone="review"] .hint .undo')`),
    "the cross takes a review picture off and offers Undo");
  await p.submit();
  check(await p.evaluate(REVIEW) === 0, "the review picture taken off is gone from the page");
  await send("Emulation.clearDeviceMetricsOverride");

  // ---- the card of a closed trade, made into a PNG by the page itself. This is
  // the proof the tests cannot give: that the canvas is not tainted, that the
  // picture is the size it is said to be, and that a phone scans the QR code
  await p.goto(B + "/");
  const closed = await p.evaluate(`(async () => {
    const links = [...new Set([...document.querySelectorAll('a[href^="/trade/"]')]
      .map(a => a.getAttribute("href").split("?")[0].slice(7)))];
    // the trade page names the card only when there is one, so no 404 is
    // provoked here that the run would count as an error
    for (const id of links) {
      const text = await (await fetch("/trade/" + id)).text();
      const at = text.indexOf('href="/share/card/');
      if (at >= 0) return text.slice(at + 18).split(/["?]/)[0];
    }
    return "";
  })()`);
  check(closed !== "", "the demo journal has a closed trade with a card");
  await p.goto(B + "/share/card/" + closed);
  const made = JSON.parse(await p.evaluate(`(async () => {
    const blob = await card_png();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let text = "";
    for (let i = 0; i < bytes.length; i += 8192)
      text += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return JSON.stringify({type: blob.type, b64: btoa(text)});
  })()`));
  const png = Buffer.from(made.b64, "base64");
  check(made.type === "image/png" && png.subarray(1, 4).toString() === "PNG"
        && png.readUInt32BE(16) === 1200 && png.readUInt32BE(20) === 675,
    "card_png makes a PNG of 1200 by 675 from the card");
  const keep = process.argv[4];
  if (keep) mkdirSync(keep, { recursive: true });
  const folder = keep || mkdtempSync(join(tmpdir(), "plainbook-card-"));
  const file = join(folder, "card-" + closed + ".png");
  writeFileSync(file, png);
  const scan = spawnSync("zbarimg", ["--quiet", "--raw", file], { encoding: "utf8" });
  if (scan.error) console.log("skipped: zbarimg is not installed, the QR code of the card was not scanned");
  else check(scan.stdout.trim() === "https://github.com/stop-loss-enjoyer/plainbook",
    "zbarimg reads the address off the PNG of the card: " + scan.stdout.trim());
  if (!keep) rmSync(folder, { recursive: true, force: true });
  check(await p.evaluate(`document.querySelectorAll('.bar button').length === 2
    && /Back/.test(document.querySelector('.bar a').textContent)`),
    "the strip over the card has Copy image, Download and Back");
  // the fonts of a machine are not known to the server: a name that draws wider
  // than its estimate is pressed back by the page, short of the candle
  check(await p.evaluate(`(() => {
    const n = document.getElementById("card-pair");
    n.textContent = "m".repeat(40);
    n.removeAttribute("textLength");
    n.setAttribute("font-size", "62");
    card_fit();
    return n.getBBox().x + n.getBBox().width <= 806;
  })()`), "a name wider than its estimate stops short of the candle");
  await send("Emulation.setDeviceMetricsOverride",
    { width: 390, height: 800, deviceScaleFactor: 1, mobile: true });
  await p.goto(B + "/share/card/" + closed);
  check(await p.evaluate(`document.documentElement.scrollWidth <= innerWidth
    && document.querySelector('#card-svg').getBoundingClientRect().width <= innerWidth`),
    "the card shrinks to a phone and the page does not scroll sideways");
  await send("Emulation.clearDeviceMetricsOverride");

  // ---- a picture of your own as the background: added through the real form
  // (the file input of the strip, which sends it the moment it is picked),
  // chosen, made into a PNG by the page, and the code read off that PNG. The
  // code stands on a picture in its small candle, 5 px a module, so it is read
  // again from a copy at 600 px wide, the size it gets in a feed
  const bits = (kind, data) => {
    const body = Buffer.concat([Buffer.from(kind), data]);
    const head = Buffer.alloc(4); head.writeUInt32BE(data.length);
    const tail = Buffer.alloc(4); tail.writeUInt32BE(crc32(body));
    return Buffer.concat([head, body, tail]);
  };
  const w = 320, h = 180, rows = [];
  for (let y = 0; y < h; y++) {
    const row = Buffer.alloc(1 + w * 3);
    for (let x = 0; x < w; x++) { row[1 + x * 3] = x * 255 / w; row[2 + x * 3] = y * 255 / h; row[3 + x * 3] = 150; }
    rows.push(row);
  }
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(w); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const small = Buffer.concat([Buffer.from("\x89PNG\r\n\x1a\n", "latin1"), bits("IHDR", ihdr),
    bits("IDAT", deflateSync(Buffer.concat(rows))), bits("IEND", Buffer.alloc(0))]);
  const pictures = mkdtempSync(join(tmpdir(), "plainbook-bg-"));
  const mine = join(pictures, "background.png");
  writeFileSync(mine, small);
  await p.goto(B + "/share/card/" + closed);
  await send("DOM.enable");
  const root = await send("DOM.getDocument", { depth: 0 });
  const field = await send("DOM.querySelector",
    { nodeId: root.result.root.nodeId, selector: "input[type=file]" });
  events.length = 0;
  await send("DOM.setFileInputFiles", { nodeId: field.result.nodeId, files: [mine] });
  await loaded();
  check((await p.url()).includes("bg=background") && await p.evaluate(
      `!!document.querySelector('#card-svg image') && !!document.querySelector('a.thumb.on img')`),
    "a picture added through the form is kept, chosen and drawn on the card");
  const onPicture = JSON.parse(await p.evaluate(`(async () => {
    const blob = await card_png();
    const bytes = new Uint8Array(await blob.arrayBuffer());
    let text = "";
    for (let i = 0; i < bytes.length; i += 8192)
      text += String.fromCharCode(...bytes.subarray(i, i + 8192));
    return JSON.stringify({b64: btoa(text)});
  })()`));
  const withPicture = Buffer.from(onPicture.b64, "base64");
  check(withPicture.readUInt32BE(16) === 1200 && withPicture.readUInt32BE(20) === 675,
    "card_png makes 1200 by 675 from a card with a picture, the canvas not tainted");
  const picturePng = join(pictures, "card-on-picture.png");
  writeFileSync(picturePng, withPicture);
  if (keep) writeFileSync(join(keep, "card-on-picture.png"), withPicture);
  const wanted = "https://github.com/stop-loss-enjoyer/plainbook";
  const first = spawnSync("zbarimg", ["--quiet", "--raw", picturePng], { encoding: "utf8" });
  if (first.error) console.log("skipped: zbarimg is not installed, the code on the picture was not scanned");
  else {
    check(first.stdout.trim() === wanted, "zbarimg reads the address off the card on a picture");
    const small600 = join(pictures, "card-600.png");
    // a posted picture is shown about this wide; the dark edge of the small
    // candle is what lets a scanner find the code on a bright picture at this size
    const shrink = [picturePng, "-filter", "Triangle", "-resize", "600x", small600];
    let made = spawnSync("magick", shrink);
    if (made.error) made = spawnSync("convert", shrink);
    if (made.error) console.log("skipped: ImageMagick is not installed, the 600 px copy was not scanned");
    else check(spawnSync("zbarimg", ["--quiet", "--raw", small600], { encoding: "utf8" }).stdout.trim() === wanted,
      "zbarimg reads the address off a copy of the card 600 px wide");
  }
  // taking it off again: the cross of the strip, the browser asked to confirm
  await p.evaluate(`window.confirm = () => true`);
  events.length = 0;
  await send("Runtime.evaluate", { expression: `document.querySelector('.pic form').requestSubmit()` });
  await loaded();
  check(!(await p.evaluate(`!!document.querySelector('a.thumb img')`))
        && !(await p.url()).includes("bg="),
    "the cross takes the picture off and the card is standard again");
  // a picture with the signature and the end of a PNG and nothing between them
  // that opens: the server cannot tell, the page can, and it makes no file of it
  const hollow = join(pictures, "hollow.png");
  writeFileSync(hollow, Buffer.concat([Buffer.from("\x89PNG\r\n\x1a\n", "latin1"),
    Buffer.from("this is no picture, only the shape of one"), bits("IEND", Buffer.alloc(0))]));
  await p.goto(B + "/share/card/" + closed);
  const again = await send("DOM.getDocument", { depth: 0 });
  const hole = await send("DOM.querySelector",
    { nodeId: again.result.root.nodeId, selector: "input[type=file]" });
  events.length = 0;
  await send("DOM.setFileInputFiles", { nodeId: hole.result.nodeId, files: [hollow] });
  await loaded();
  await sleep(300);
  check(await p.evaluate(`[...document.querySelectorAll('.bar > button')].every(
      b => b.textContent === 'This picture does not open' && b.disabled)`)
        && await p.evaluate(`card_png().then(() => "made", e => e.message)`)
           === "This picture does not open",
    "a picture that does not decode says so on the buttons and makes no file");
  await p.evaluate(`window.confirm = () => true`);
  events.length = 0;
  await send("Runtime.evaluate", { expression: `document.querySelector('.pic form').requestSubmit()` });
  await loaded();
  rmSync(pictures, { recursive: true, force: true });
}

let failed = false;
try { await run(api); }
catch (e) { failed = true; console.log("FAILED:", e.message); }
if (errors.length) { failed = true; console.log("console/page errors:"); for (const e of errors) console.log("  " + e); }
else console.log("no page errors");
await finish(failed ? 1 : 0);

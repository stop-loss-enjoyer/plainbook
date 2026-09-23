// The forms of the journal driven in a real (headless) browser: the tests go
// around the page scripts, and this is the one check that runs them. Needs
// Chromium and Node 22 or newer, nothing else. Run it against a FRESH demo
// journal, never against the owner's:
//
//   python3 tools/demo_journal.py /tmp/pb-demo
//   PLAINBOOK_ROOT=/tmp/pb-demo PLAINBOOK_PORT=8899 python3 -m plainbook.server &
//   node tools/browser_check.mjs http://127.0.0.1:8899
//
// Every line printed "ok:" is a step that behaved; the run stops at the first
// that did not, and any error the page logged is printed at the end. The one
// 400 it logs on purpose is the playbook form refusing rules changed under a
// held version.
import { spawn } from "node:child_process";
import { setTimeout as sleep } from "node:timers/promises";

const PORT = 9333;
const B = process.argv[2] || "http://127.0.0.1:8899";
const PROFILE = process.argv[3] || "/tmp/plainbook-browser-check-profile";
const chrome = spawn("chromium", ["--headless=new", `--remote-debugging-port=${PORT}`,
  "--no-first-run", "--no-default-browser-check", "--disable-gpu",
  `--user-data-dir=${PROFILE}`,
  "about:blank"], { stdio: "ignore" });
process.on("exit", () => chrome.kill());

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
  await new Promise(res => {
    const t = setInterval(() => {
      const i = events.findIndex(m => m.method === "Page.loadEventFired");
      if (i >= 0) { events.splice(i, 1); clearInterval(t); res(); }
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
  // submit a form and wait for the page that comes after
  async submit(selector = "form") {
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
  const balance = await p.evaluate(`JSON.parse(document.querySelector('form').dataset.balances)[document.querySelector('[name=account]').value]`);
  check(balance > 0, "the form carries the balance of the account: " + balance);
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
  await p.goto(B + "/card/" + DAY);                 // the day the trade above closed
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
  check(await has(`document.querySelector('textarea[name=best]').value`, label),
    "the card came back with the trade in the best trade");

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
}

let failed = false;
try { await run(api); }
catch (e) { failed = true; console.log("FAILED:", e.message); }
if (errors.length) { failed = true; console.log("console/page errors:"); for (const e of errors) console.log("  " + e); }
else console.log("no page errors");
chrome.kill();
process.exit(failed ? 1 : 0);

# Sticky Header Rework Implementation Plan

## Outcome

Implemented and confirmed working on the phone.

The reliable Android Chrome fix was narrower than the original plan: instead of trying to make whole-page scrolling and sticky offsets behave everywhere, the wide `transactions` and summary tables were moved into a dedicated `.table-shell` scroll container. Their headers now stick to the top of that container with `top: 0`, while the tab bar stays sticky at the page level.

Final implementation notes:
- `templates/transactions.html` and `templates/summary.html` wrap their tables in `<div class="table-shell">`
- `static/style.css` defines `.table-shell` with `overflow: auto`, `max-width: 100%`, touch scrolling, and a mobile `max-height`
- `thead th` and `.recent-hdr` no longer depend on a hardcoded `top: 44px`
- `templates/base.html` measures the actual tabs height into `--tabs-height` for mobile sizing

Phone deployment notes:
- Source files were pushed directly to `/sdcard/projects/blog7` via `adb push`
- Termux app launch remains `cd /sdcard/projects/blog7 && python app.py`
- SSH to Termux was verified as `u0_a552@10.0.0.53:8022`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tabs and table headers stay frozen at the top of the viewport when scrolling, on both Balances (`/`) and Transactions (`/transactions`).

**Architecture:** Delete the JS clone in `base.html` and rely on pure CSS `position: sticky`. Fix the three bugs keeping sticky from working today: (1) `.recent-hdr` has no sticky rule, (2) `<thead>` wrapper is missing in `transactions.html`, (3) an ancestor `<div class="tbl-wrap">` with `overflow: auto` is creating a scroll container that silently kills descendant sticky. Offset headers by the tabs height (44px) so they stack rather than collide at `top:0`.

**Tech Stack:** Flask templates (Jinja2), plain CSS, Playwright (local harness at `~/blog7-playwright/snap.js`) for visual verification. No test framework in the project — verification is "screenshot in Playwright, confirm the header stays pinned."

**Deploy loop:** edit on laptop → `git push` → SSH to phone and `git pull && pkill -f 'python app.py' && nohup python app.py > ~/blog7.log 2>&1 & disown` → screenshot via local Playwright.

---

### Task 1: Add sticky rule to `.recent-hdr` (Balances page)

**Files:**
- Modify: `static/style.css:49-50`

- [ ] **Step 1: Edit `.recent-hdr` rule**

Change lines 49–50 from:

```css
.recent-hdr { display: flex; gap: 4px; font-weight: bold; color: #555;
              padding: 4px 0 4px; border-bottom: 1px solid #ddd; }
```

to:

```css
.recent-hdr { display: flex; gap: 4px; font-weight: bold; color: #555;
              padding: 4px 0 4px; border-bottom: 1px solid #ddd;
              position: sticky; top: 44px; background: #fff; z-index: 5; }
```

- [ ] **Step 2: Commit**

```bash
git add static/style.css
git commit -m "Pin balances log header with position: sticky"
```

---

### Task 2: Fix `thead th` sticky offset and wrap transactions `<tr>` in `<thead>`

**Files:**
- Modify: `static/style.css:90`
- Modify: `templates/transactions.html:12-19`

- [ ] **Step 1: Change `thead th` sticky offset in `static/style.css:90`**

From:

```css
thead th { position: sticky; top: 0; background: #fff; z-index: 1; }
```

To:

```css
thead th { position: sticky; top: 44px; background: #fff; z-index: 5; }
```

- [ ] **Step 2: Wrap header row in `<thead>` in `templates/transactions.html`**

Change lines 11–19 from:

```html
<table>
  <tr>
    <th>{{ sort_link('Date', 'day') }}</th>
    <th>{{ sort_link('Desc', 'label') }}</th>
    <th>{{ sort_link('Asset', 'asset_id') }}</th>
    <th>{{ sort_link('Flow', 'flow') }}</th>
    <th>{{ sort_link('Amt', 'amt') }}</th>
    <th>{{ sort_link('Bal', 'balance') }}</th>
  </tr>
```

To:

```html
<table>
  <thead>
  <tr>
    <th>{{ sort_link('Date', 'day') }}</th>
    <th>{{ sort_link('Desc', 'label') }}</th>
    <th>{{ sort_link('Asset', 'asset_id') }}</th>
    <th>{{ sort_link('Flow', 'flow') }}</th>
    <th>{{ sort_link('Amt', 'amt') }}</th>
    <th>{{ sort_link('Bal', 'balance') }}</th>
  </tr>
  </thead>
```

- [ ] **Step 3: Commit**

```bash
git add static/style.css templates/transactions.html
git commit -m "Offset thead sticky below tabs; use <thead> on transactions"
```

---

### Task 3: Remove sticky-killing ancestor `<div class="tbl-wrap">`

**Files:**
- Modify: `templates/transactions.html:10,34`
- Modify: `static/style.css:82-86` (delete unused rules)

**Why:** `.tbl-wrap` sets `overflow: auto`, which turns it into a scroll container. `position: sticky` on descendants then sticks to THAT container's top edge, not the viewport — and since the container is short, sticky does nothing. Must be removed for CSS sticky to work on mobile Chrome.

- [ ] **Step 1: Remove the wrapper in `templates/transactions.html`**

Delete line 10 (`<div class="tbl-wrap">`) and line 34 (`</div>`). The `<table>` should now be a direct child of the block content.

- [ ] **Step 2: Delete unused table-wrap CSS in `static/style.css:82-86`**

Delete these five lines:

```css
.tbl-wrap { overflow: auto; -webkit-overflow-scrolling: touch; margin-top: 8px; }
.tbl-header-wrap { overflow: hidden; }
.tbl-body-wrap   { overflow: auto; -webkit-overflow-scrolling: touch;
                   height: calc(100vh - 120px); }
.tbl-hdr { border-collapse: separate; border-spacing: 0; font-size: 12px; }
```

(Grepped: these classes are used nowhere else once `.tbl-wrap` is removed from transactions.html — summary.html uses inline styles, not these classes.)

- [ ] **Step 3: Audit other templates for sticky-killers**

Run:

```bash
grep -rn "overflow\|transform\|filter:" templates/ static/style.css
```

Expected: no `overflow: hidden`, `overflow: auto`, `transform`, or `filter` on any ancestor of `.content`, `.recent-hdr`, `table`, or `thead`. The `.tabs` itself has `overflow-x: auto` — that's fine (it's the sticky element itself, not an ancestor of the sticky elements below it). If anything else turns up, investigate before proceeding.

- [ ] **Step 4: Commit**

```bash
git add templates/transactions.html static/style.css
git commit -m "Drop tbl-wrap overflow container that was killing sticky"
```

---

### Task 4: Delete the JS header-clone in `base.html`

**Files:**
- Modify: `templates/base.html:27-58`

- [ ] **Step 1: Delete lines 27–58**

Remove the entire `<script>...</script>` block (the `DOMContentLoaded` handler that creates `fixDiv`, clones `hdr`, and runs `requestAnimationFrame(tick)`).

The resulting `base.html` should end:

```html
    {% block content %}{% endblock %}
  </div>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add templates/base.html
git commit -m "Remove JS header clone; pure-CSS sticky now handles it"
```

---

### Task 5: Push, deploy to phone, verify

**Files:** none (verification only)

- [ ] **Step 1: Push**

```bash
cd ~/projects/blog7 && git push
```

- [ ] **Step 2: Pull on phone and restart Flask**

```bash
ssh -p 8022 -i ~/.ssh/id_ed25519 u0_a552@10.0.0.53 "cd /sdcard/projects/blog7 && git pull && pkill -f 'python app.py'; sleep 1; nohup python app.py > ~/blog7.log 2>&1 & disown"
```

Expected: `Fast-forward` or `Already up to date.` Then flask restarts (ignore pkill exit code if no process was running).

- [ ] **Step 3: Wait for bind, confirm port open**

```bash
sleep 3 && powershell -Command "Test-NetConnection -ComputerName 10.0.0.53 -Port 5000 -InformationLevel Quiet"
```

Expected: `True`

- [ ] **Step 4: Screenshot Balances scrolled**

```bash
cd ~/blog7-playwright && node -e "
const {chromium} = require('playwright');
(async()=>{
  const b = await chromium.launch();
  const c = await b.newContext({viewport:{width:412,height:600},deviceScaleFactor:2});
  const p = await c.newPage();
  await p.goto('http://10.0.0.53:5000/',{waitUntil:'networkidle'});
  await p.evaluate(()=>window.scrollTo(0,500));
  await p.waitForTimeout(300);
  await p.screenshot({path:'verify_bal.png'});
  const s = await p.evaluate(()=>{
    const h = document.querySelector('.recent-hdr');
    return { top: h && h.getBoundingClientRect().top, pos: h && getComputedStyle(h).position };
  });
  console.log(JSON.stringify(s));
  await b.close();
})();
"
```

Expected output: `{"top":44,"pos":"sticky"}` (or very close to 44 — within ±2px). Read `verify_bal.png` — header row "Date / Amount / Type / Balance" should be pinned directly below the tabs.

- [ ] **Step 5: Screenshot Transactions scrolled**

```bash
cd ~/blog7-playwright && node -e "
const {chromium} = require('playwright');
(async()=>{
  const b = await chromium.launch();
  const c = await b.newContext({viewport:{width:412,height:700},deviceScaleFactor:2});
  const p = await c.newPage();
  await p.goto('http://10.0.0.53:5000/transactions',{waitUntil:'networkidle'});
  await p.evaluate(()=>window.scrollTo(0,1200));
  await p.waitForTimeout(300);
  await p.screenshot({path:'verify_tx.png'});
  const s = await p.evaluate(()=>{
    const th = document.querySelector('thead th');
    return { top: th && th.getBoundingClientRect().top, pos: th && getComputedStyle(th).position };
  });
  console.log(JSON.stringify(s));
  await b.close();
})();
"
```

Expected: `{"top":44,"pos":"sticky"}`. Read `verify_tx.png` — "Date / Desc / Asset / Flow / Amt / Bal" should be pinned directly below the tabs, column widths aligned with the body rows below.

- [ ] **Step 6: If both screenshots show frozen headers, update memory**

Delete `~/.claude/projects/C--Users-donal-projects-blog7/memory/project_sticky_header_fix.md` and remove its line from `MEMORY.md` — the work is done.

---

## Rollback

If mobile Chrome on the phone still fails sticky after Task 3 (some other ancestor found with `overflow`/`transform`), the fallback is to keep the JS clone but fix the width mismatch: set `fixTbl.style.width = tbl.offsetWidth + 'px'` and copy each original `th.offsetWidth` to the cloned `th`. Don't do this preemptively.

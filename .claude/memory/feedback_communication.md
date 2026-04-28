---
name: Communication style feedback
description: User wants direct answers and clear single instructions, not diagnostic loops
type: feedback
originSessionId: 6a8b20c8-ee7e-4acb-b1c5-0447a9f76f2e
---
When the user says "page is up" or similar — believe them and act immediately. Do not run verification commands first.

**Why:** User was repeatedly frustrated when Claude kept re-checking Flask status instead of just proceeding after being told it was up.

**How to apply:** If the user reports a state (server up, page loaded, button pressed), trust it and give the next clear action. Only verify if something actually fails.

---

Give one clear instruction at a time when the user needs to do something manually.

**Why:** User lost track of what was needed when Claude ran diagnostics and asked questions simultaneously instead of giving a single concrete next step.

**How to apply:** When user action is needed, say exactly one thing: "Press Sync EBT" or "Open Termux and run X". Don't bundle it with questions or diagnostic output.

---

Don't ask for confirmation before doing routine git commit/push/pull sequences.

**Why:** User said "I don't care" when asked — they trust Claude to handle these without checking.

**How to apply:** Commit, push, pull as needed without prompting. Only pause for destructive or irreversible actions.

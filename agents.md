# blog7 — Local Workspace Map & Router (Layer 2)

**Root law:** If you need the master projects map, go to the parent directory: `../agents.md`

---

## What This Project Is
A Flask web application coupled with a complex financial transaction pipeline. It is a monumental system representing months of heavy, hard-fought engineering effort. 

The core mission is **Data Reconciliation**: uniting and matching two highly divergent financial data streams:
1. **Raw Bank Statements** (CSV/PDF statement files).
2. **Netspend API Transactions** (real-time API responses, utilizing tokens inside `projects/secrets/finance/`).

The actual core Python pipeline modules reside inside the proper nested python structure at **`C:\Users\donal\projects\finance\finance\`**.

---

## 🔄 blog7 Financial Reconciliation Pipeline
Every task in this workspace must progress sequentially through these stages:
1. **Stage 1: Statement & API Intake** — Parse the raw statements and fetch the latest Netspend API JSON responses.
2. **Stage 3: Divergent Stream Reconciliation** — Run matching algorithms to align statement records with Netspend's API records (resolving dates, amounts, and duplicate transactions).
3. **Stage 4: Database Update** — Safely append reconciled entries to `finance.db` and `blog7.db` inside your data directory.
4. **Stage 5: Flask Visualization** — Run and test `app.py` to verify the financial dashboards and UI.

---

## 🚦 Local Context Routing Table (AI Shielding)
This table protects your context window. It locks the AI's attention *only* on active files and explicitly tells it to **never read or touch your archive of obsolete `.py` scripts**, keeping your historical files completely safe and untouched:

| Current Objective / Task | Read/Load Files (In-Scope) | Skip/Ignore Files (Out-of-Scope) | Required MCP Tools |
| :--- | :--- | :--- | :--- |
| **Flask UI / Dashboard Dev** | `app.py`, `templates/`, `static/` | All `finance/` scripts, obsolete code | None (pure layout editing) |
| **Path Configuration** | `dpc_paths.py` | Core Flask logic, database binaries | None |
| **API Sync & Data Pull** | `finance/finance/` active modules, secrets | **All Obsolete `.py` scripts**, old code | Web fetching / Curl |
| **Database Schema / Queries** | `dpc_paths.py`, `db/` schema files | Statements, HTML files | SQL database explorers |

---

## 📝 Key Active Files Directory
* **`app.py`** — The core Flask web server and routing file (sort-of fixed, active, and needs careful, bug-free maintenance).
* **`dpc_paths.py`** — Handles device-relative mappings for laptop and phone.
* **`finance/finance/`** — The authoritative, proper Python package folder containing your active data-flow and updater scripts.

---

## 🔒 Protected Obsolete & Historical Archive (DO NOT EDIT/DELETE)
These scripts are valuable historical records of your month-long development cycle. They must **never** be touched, modified, or cleaned up by any AI:
* *All raw, older `.py` scripts sitting in the project roots.*
* *Any unmapped utility scripts not explicitly listed under Active Files.*

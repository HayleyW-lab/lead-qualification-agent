# Project Journal — Lead Follow-Up and Qualification Agent

A running log of how this project was actually built: the decisions made, why they were made, and what each phase delivered. Kept as a build-in-public style journal rather than a polished write-up, so it reflects the real process — including the mistakes and fixes.

---

## Setup — Environment and first connection

**Goal:** Get a working Python environment talking to the Gemini API before writing any agent logic.

**Steps:**
1. Created a Google AI Studio account and generated a Gemini API key
2. Set up the local project: virtual environment (`venv`), `.env` file for the API key, `.gitignore` to keep the key and environment out of version control
3. Installed `google-genai` (official Gemini SDK) and `python-dotenv`
4. Wrote a minimal `test_connection.py` to confirm the key, SDK, and environment were all working together

**Issues hit and resolved:**
- `gemini-2.5-flash` returned a 404 — deprecated for new API keys. Fixed by calling `client.models.list()` to ask the API directly which models the key actually had access to, rather than guessing from documentation that may be outdated. Landed on `gemini-3.5-flash`.
- A venv got moved to a different folder location and broke, because virtual environments store absolute paths internally. Fixed by deleting and recreating the venv in its final location. **Lesson:** finalise a project's folder structure before creating the venv, or recreate it after any move.

**Outcome:** Confirmed working connection to Gemini before any agent logic was written — a deliberate checkpoint before building further.

---

## Phase 0 — Design and schema

Before writing the qualification prompt, the lead schema was designed deliberately, drawing on real SaaS sales/CS experience rather than a generic template:

- **Fit vs. Readiness split** — separated "is this the right kind of customer?" (fit, based on an Ideal Customer Profile) from "are they ready to buy right now?" (readiness, based on BANT). Conflating these two is a mistake often made in real sales orgs.
- **BANT, adapted with real judgement** rather than applied rigidly:
  - An undefined or vague budget is not automatically a bad sign — often it means an early-stage lead who hasn't been educated on their own need yet, not a low-quality one.
  - Bad timing (e.g. a company mid-EOFY reporting) is not a reason to disqualify — it's a reason to schedule a follow-up for after the timing clears.
- **Firmographic/fit fields added** beyond textbook BANT: company size, staff/client counts, and existing software/integration needs — because real leads are as much about *whether they're the right customer* as *whether they're ready to buy*.
- **Input designed to be channel-agnostic** — raw text covers both a written enquiry (web form, email) and a call transcript, since real leads arrive both ways.
- **Output extended iteratively** as more real-world scenarios were recalled: added "Book demo" / "Educate + nurture" / "Follow up later" (with a specific follow_up_timing field) / "Disqualify" as the four next-action outcomes.

**Outcome:** A schema that reflects actual SaaS sales judgement, not a generic AI framework — the throughline for the whole project's portfolio value.

---

## Phase 1 — Core agent, batch processing, and error handling

**Goal:** Move from a single hardcoded test script to a tool that can process multiple real leads reliably.

### 1. Core agent (`lead_agent.py`)
- Built `qualify_lead()` — takes raw lead text + source, sends it to Gemini with a detailed system prompt encoding the fit/readiness schema above
- Used Gemini's structured output mode (`response_schema`) to force strict, valid JSON every time — not just prose asked nicely to be JSON. This makes the output reliably usable by other code (a UI, a CRM write-back, a spreadsheet) without brittle text-parsing.
- Tested against three deliberately chosen scenarios: a clean hot lead, an early-stage lead with no defined budget, and a good-fit-but-bad-timing (EOFY) lead — each designed to test one of the domain judgement rules explicitly.

**Result:** All three test cases came back with correct scoring *and* reasoning that explicitly referenced the right domain rule (e.g. "budget is undefined but need is strong, so this reads as early-stage rather than low quality") — confirming the prompt was encoding real judgement, not generic BANT.

### 2. Batch processing (`batch_process.py`)
- Built `leads.csv` as a sample input file — mirrors what a CRM export might look like
- `load_leads()` reads the CSV; `process_leads()` loops through every lead calling `qualify_lead()`
- Results saved to a timestamped output CSV (`results_YYYYMMDD_HHMMSS.csv`) so re-runs never overwrite previous results — useful for comparing before/after a prompt change

### 3. Error handling and rate limiting
- Each API call wrapped in try/except — a single lead failing doesn't crash the whole batch; it's logged with `status: error` and the batch continues
- Added a 7-second pause between calls to stay under the free tier's 10 requests/minute limit
- Added **retry logic with backoff**: transient errors (e.g. `503 UNAVAILABLE` — "model is currently experiencing high demand") are retried up to 3 times with a wait; non-transient errors (bad key, malformed request) fail immediately rather than wasting time retrying something that will never succeed

**Real-world validation:** During testing, a live `503` error actually occurred (Gemini's servers were temporarily overloaded). The batch correctly logged it and continued processing the remaining leads without crashing — proving the error handling on a genuine failure, not just a simulated one.

### 4. A real prompt-engineering fix
Batch testing included two deliberately tricky leads beyond the original three: a near-empty "just checking prices" enquiry, and a 200-person enterprise lead requesting a multi-million dollar, board-level, 18-month RFP procurement process.

The enterprise lead initially scored **"Strong fit / Book demo"** — the agent was treating a large budget and clear need as automatically good, without weighing whether the *company* was actually the right customer. This is a known real-world sales mistake: chasing an exciting "big logo" that's actually the wrong fit.

**Fix:** Added an explicit Ideal Customer Profile (ICP) definition to the system prompt — SMB to mid-market, roughly 5–250 staff — with an explicit instruction that enterprise-scale procurement (formal RFPs, multi-department rollouts, board-level sign-off) should be scored "Poor" fit *regardless* of deal size.

**Result after the fix:** The same lead correctly scored **"Poor fit / Disqualify"**, with reasoning that explicitly weighed the trade-off: *"the headcount of 200 technically fits our mid-market bracket, but this is a board-level, multi-department ERP replacement with a multi-million budget and formal RFP process... we must disqualify this lead despite the attractive budget."*

This was a genuine before/after proof point: the fix changed an actual decision, not just the wording — evidence that the prompt engineering was working correctly, not just sounding plausible.

**Outcome:** Phase 1 complete. The agent reliably processes batches of leads, handles real API failures gracefully, respects rate limits, and its fit-scoring logic has been tested and corrected against a genuine edge case.

---

## What's next

- **Phase 2 (remainder):** deliberate edge case testing — very vague leads, spam-like enquiries, unusual tone, non-English text, empty input
- **Phase 3:** a simple interface (CLI or lightweight UI) so someone other than the developer can try it; a sample dataset bundled in the repo for demoing without an API key
- **Phase 4:** integration into the portfolio site (ahayleyoriginal.dev), alongside KiwiPool and WriteHero

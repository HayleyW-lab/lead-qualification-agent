# Lead Follow-Up and Qualification Agent

An AI-powered agent that reads raw, unstructured lead enquiries (web form messages, call transcripts, referral notes) and qualifies them using real B2B SaaS sales and customer success judgement — not just a generic textbook framework.

Built as a portfolio project to demonstrate both commercial sales/CS instinct and technical build skills.

## Why this project

Most lead-scoring tools apply BANT (Budget, Authority, Need, Timeline) rigidly. In practice, that misses a lot of real signal:

- An undefined budget doesn't always mean a bad lead — often it means the prospect hasn't been educated on their own need yet.
- Bad timing (e.g. a company mid-way through end-of-financial-year reporting) isn't a reason to disqualify — it's a reason to schedule a follow-up.

This agent encodes that kind of judgement directly into the prompt, based on real experience running SaaS sales, implementation, and ~100 weekly retention calls in a prior career.

## What it does

Given a raw lead (text or call transcript), the agent returns structured JSON covering:

- **Fit** — company size, integration needs, overall fit score
- **Readiness** — budget, authority, need, and timeline signals (BANT-based)
- **Reasoning** — a plain-English explanation of the read, the way an experienced rep would explain it to a colleague
- **Next action** — Book demo / Educate + nurture / Follow up later / Disqualify, with a suggested follow-up window where relevant

## Tech stack

- Python
- Google Gemini API (`gemini-3.5-flash`) via Google AI Studio, free tier
- Structured JSON output enforced via Gemini's response schema
- `python-dotenv` for secure local API key handling

## Example

**Input:**

> "This looks like exactly what we need but we're heads down on EOFY reporting right now, can you check back with us in a few weeks once that's done and we know our numbers for next year."

**Output:**

```json
{
  "fit_score": "Strong",
  "readiness_score": "Warm",
  "next_action": "Follow up later",
  "follow_up_timing": "In 3-4 weeks (mid-July, post-EOFY) once their new budget and numbers are finalized",
  "reasoning": "Strong fit... budget is not yet formed due to EOFY reporting, the lead is highly qualified and explicitly requested a follow-up..."
}
```

## Setup

1. Clone the repo
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `source venv/Scripts/activate` (Git Bash / Mac / Linux)
4. Install dependencies: `pip install google-genai python-dotenv`
5. Create a `.env` file with your own key: `GEMINI_API_KEY=your_key_here`
6. Run: `python lead_agent.py`

## Status

Early-stage portfolio build. Core qualification logic is working and tested against sample leads reflecting real-world SaaS sales scenarios. Next steps: batch processing of multiple leads, and a simple interface for feeding in real (anonymised) lead data.

## About

Built by Hayley Wilson — Auckland-based, career-changing into tech after 10+ years in SaaS sales, implementation, and customer success. More projects at [ahayleyoriginal.dev](https://ahayleyoriginal.dev).

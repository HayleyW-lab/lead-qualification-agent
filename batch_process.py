import csv
import sys
import time
from datetime import datetime
from lead_agent import qualify_lead

# Usage: python batch_process.py [input_file]
# Defaults to leads.csv if no argument is given
INPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "leads.csv"
OUTPUT_FILE = f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

# Free tier rate limit is 10 requests/minute on gemini-3.5-flash.
# Sleeping 7 seconds between calls keeps us safely under that
# (≈8-9 requests/minute), without making the batch painfully slow.
SECONDS_BETWEEN_CALLS = 7

# Retry settings for transient errors (e.g. 503 "model overloaded").
# These are temporary server-side issues, not problems with our request,
# so a short wait-and-retry usually resolves them.
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 15

OUTPUT_COLUMNS = [
    "source",
    "lead_text",
    "fit_score",
    "readiness_score",
    "company_size_signal",
    "integration_needs",
    "budget_signal",
    "authority_signal",
    "need_signal",
    "timeline_signal",
    "next_action",
    "follow_up_timing",
    "reasoning",
    "status",       # "success" or "error"
    "error_detail", # blank unless status is "error"
]


def load_leads(filepath):
    """Reads a leads CSV and returns a list of dicts with 'source' and 'text'."""
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def qualify_retry_wrapper(lead):
    """
    Calls qualify_lead(), retrying if the failure looks transient
    (e.g. '503 UNAVAILABLE' when the model is temporarily overloaded).
    Non-transient errors (bad API key, malformed request, etc.) are
    raised immediately rather than wasting time retrying something
    that will never succeed.
    """
    transient_markers = ["503", "UNAVAILABLE", "overloaded", "high demand"]

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return qualify_lead(lead["text"], source=lead["source"])
        except Exception as e:
            last_error = e
            is_transient = any(marker in str(e) for marker in transient_markers)

            if not is_transient or attempt == MAX_RETRIES:
                raise

            print(f"  (transient error, retrying in {RETRY_WAIT_SECONDS}s — attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_WAIT_SECONDS)

    raise last_error


def process_leads(leads):
    """
    Runs each lead through qualify_lead(). If a lead fails (API error,
    malformed response, etc.), it's logged with status='error' and the
    batch continues rather than crashing.
    """
    results = []

    for i, lead in enumerate(leads, start=1):
        print(f"Processing lead {i}/{len(leads)} (source: {lead['source']})...")

        row = {
            "source": lead["source"],
            "lead_text": lead["text"],
        }

        try:
            result = qualify_retry_wrapper(lead)
            row.update(result)
            row["status"] = "success"
            row["error_detail"] = ""
            print(f"  -> {result['readiness_score']} / {result['fit_score']} / {result['next_action']}")

        except Exception as e:
            # Catches API errors, network issues, malformed JSON, etc.
            # We log the failure and keep going instead of stopping the batch.
            row["status"] = "error"
            row["error_detail"] = str(e)
            print(f"  -> FAILED: {e}")

        results.append(row)

        # Rate limiting: skip the wait after the very last lead
        if i < len(leads):
            time.sleep(SECONDS_BETWEEN_CALLS)

    return results


def save_results(results, filepath):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in results:
            # Fill any missing columns (e.g. failed leads won't have
            # fit_score, reasoning, etc.) with blanks so the CSV stays valid
            full_row = {col: row.get(col, "") for col in OUTPUT_COLUMNS}
            writer.writerow(full_row)


if __name__ == "__main__":
    leads = load_leads(INPUT_FILE)
    print(f"Loaded {len(leads)} leads from {INPUT_FILE}\n")

    results = process_leads(leads)

    save_results(results, OUTPUT_FILE)

    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = len(results) - success_count

    print(f"\nDone. {success_count} succeeded, {error_count} failed.")
    print(f"Results saved to {OUTPUT_FILE}")

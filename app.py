import time
import io
import csv
import pandas as pd
import streamlit as st
from lead_agent import qualify_lead

MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5  # shorter than batch_process.py since this is interactive — a user is waiting

st.set_page_config(page_title="Lead Qualification Agent", page_icon="📊", layout="centered")

st.title("📊 Lead Qualification Agent")
st.caption("AI-powered lead scoring built on real SaaS sales and customer success judgement.")


def qualify_with_retry(lead_text, source):
    """
    Calls qualify_lead(), retrying on transient errors (e.g. a temporary
    '503 model overloaded' from Gemini) before giving up. Non-transient
    errors are raised immediately rather than making the user wait
    through retries that won't help.
    """
    transient_markers = ["503", "UNAVAILABLE", "overloaded", "high demand"]
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return qualify_lead(lead_text, source=source)
        except Exception as e:
            last_error = e
            is_transient = any(marker in str(e) for marker in transient_markers)
            if not is_transient or attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_WAIT_SECONDS)

    raise last_error


# ---------------------------------------------------------------
# Colour mapping for score badges.
# Streamlit doesn't have a built-in "coloured badge" component,
# so we build small styled HTML snippets ourselves.
# ---------------------------------------------------------------
SCORE_COLORS = {
    # Fit scores
    "Strong": "#2e7d32",    # green
    "Moderate": "#f9a825",  # amber
    "Poor": "#c62828",      # red
    # Readiness scores
    "Hot": "#c62828",       # red (urgent/hot = attention-grabbing)
    "Warm": "#f9a825",      # amber
    "Cold": "#1565c0",      # blue (cold ≠ bad, just low urgency)
}


def score_badge(label: str, value: str) -> str:
    """Returns an HTML snippet rendering a coloured badge for a score value."""
    color = SCORE_COLORS.get(value, "#616161")  # grey fallback for unknown values
    return f"""
    <div style="display:inline-block; margin-right:12px; margin-bottom:8px;">
        <span style="font-size:0.85em; color:#666;">{label}</span><br/>
        <span style="background-color:{color}; color:white; padding:4px 12px;
                     border-radius:6px; font-weight:600; font-size:1.05em;">
            {value}
        </span>
    </div>
    """


# ---------------------------------------------------------------
# Session state
# ---------------------------------------------------------------
if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "history" not in st.session_state:
    st.session_state.history = []

if "batch_results" not in st.session_state:
    st.session_state.batch_results = None


tab_single, tab_batch = st.tabs(["Single Lead", "Batch Upload"])

# =================================================================
# TAB 1: Single lead qualification
# =================================================================
with tab_single:
    st.caption("Paste a raw lead enquiry below and get an instant fit + readiness assessment.")

    with st.form("lead_form"):
        lead_text = st.text_area(
            "Lead enquiry",
            height=150,
            placeholder="Paste the raw lead text here — a web form message, call transcript, email, etc.",
        )
        source = st.selectbox(
            "Source",
            ["web form", "inbound call", "email", "referral", "other"],
        )
        submitted = st.form_submit_button("Qualify Lead", type="primary")

    if submitted:
        if not lead_text.strip():
            st.warning("Please paste a lead enquiry before submitting.")
        else:
            with st.spinner("Qualifying lead... (this may retry once or twice if Gemini is briefly busy)"):
                try:
                    result = qualify_with_retry(lead_text, source)
                    st.session_state.last_result = result

                    preview = lead_text.strip().replace("\n", " ")
                    preview = preview[:80] + "..." if len(preview) > 80 else preview

                    st.session_state.history.append({
                        "Lead preview": preview,
                        "Source": source,
                        "Fit": result["fit_score"],
                        "Readiness": result["readiness_score"],
                        "Next action": result["next_action"],
                    })
                except Exception as e:
                    st.error(f"Something went wrong calling the agent: {e}")
                    st.session_state.last_result = None

    # ---- Results display ----
    if st.session_state.last_result:
        result = st.session_state.last_result

        st.divider()
        st.subheader("Result")

        badges_html = score_badge("Fit", result["fit_score"]) + score_badge("Readiness", result["readiness_score"])
        st.markdown(badges_html, unsafe_allow_html=True)

        st.markdown(f"**Next action:** {result['next_action']}")
        if result.get("follow_up_timing") and result["follow_up_timing"].lower() not in ("n/a", "none", "not applicable", ""):
            st.markdown(f"**Follow-up timing:** {result['follow_up_timing']}")

        st.markdown("**Reasoning:**")
        st.write(result["reasoning"])

        with st.expander("See full signal breakdown"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Fit signals**")
                st.write(f"- Company size: {result['company_size_signal']}")
                st.write(f"- Integration needs: {result['integration_needs']}")
            with col2:
                st.markdown("**Readiness signals (BANT)**")
                st.write(f"- Budget: {result['budget_signal']}")
                st.write(f"- Authority: {result['authority_signal']}")
                st.write(f"- Need: {result['need_signal']}")
                st.write(f"- Timeline: {result['timeline_signal']}")

    # ---- Session history ----
    if st.session_state.history:
        st.divider()
        st.subheader(f"Session history ({len(st.session_state.history)} leads)")

        readiness_counts = {}
        action_counts = {}
        for row in st.session_state.history:
            readiness_counts[row["Readiness"]] = readiness_counts.get(row["Readiness"], 0) + 1
            action_counts[row["Next action"]] = action_counts.get(row["Next action"], 0) + 1

        summary_cols = st.columns(len(readiness_counts) or 1)
        for col, (score, count) in zip(summary_cols, readiness_counts.items()):
            col.metric(score, count)

        with st.expander("Breakdown by next action"):
            for action, count in action_counts.items():
                st.write(f"- {action}: {count}")

        st.dataframe(st.session_state.history, use_container_width=True, hide_index=True)

        if st.button("Clear history"):
            st.session_state.history = []
            st.rerun()


# =================================================================
# TAB 2: Batch CSV upload
# =================================================================
with tab_batch:
    st.caption("Upload a CSV with 'source' and 'text' columns to qualify multiple leads at once.")

    st.markdown(
        "**Expected format:** two columns named `source` and `text` — "
        "matching what a CRM export or a simple spreadsheet of enquiries would look like."
    )

    uploaded_file = st.file_uploader("Upload leads CSV", type=["csv"])

    if uploaded_file is not None:
        try:
            df_preview = pd.read_csv(uploaded_file)
            uploaded_file.seek(0)  # reset so we can read it again below

            if "source" not in df_preview.columns or "text" not in df_preview.columns:
                st.error("CSV must contain 'source' and 'text' columns.")
            else:
                st.write(f"Found **{len(df_preview)}** leads in this file.")
                st.dataframe(df_preview.head(), use_container_width=True, hide_index=True)

                if st.button("Process batch", type="primary"):
                    reader = csv.DictReader(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
                    leads = list(reader)

                    progress_bar = st.progress(0, text="Starting batch...")
                    results = []

                    for i, lead in enumerate(leads, start=1):
                        progress_bar.progress(
                            i / len(leads),
                            text=f"Processing lead {i}/{len(leads)}..."
                        )
                        row = {"source": lead["source"], "lead_text": lead["text"]}
                        try:
                            result = qualify_with_retry(lead["text"], lead["source"])
                            row.update(result)
                            row["status"] = "success"
                            row["error_detail"] = ""
                        except Exception as e:
                            row["status"] = "error"
                            row["error_detail"] = str(e)
                        results.append(row)

                    progress_bar.progress(1.0, text="Done!")
                    st.session_state.batch_results = results

        except Exception as e:
            st.error(f"Couldn't read that CSV: {e}")

    # ---- Batch results display ----
    if st.session_state.batch_results:
        results = st.session_state.batch_results
        st.divider()

        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = len(results) - success_count
        st.write(f"**Done.** {success_count} succeeded, {error_count} failed.")

        # Dashboard summary for the batch
        readiness_counts = {}
        for r in results:
            if r["status"] == "success":
                readiness_counts[r["readiness_score"]] = readiness_counts.get(r["readiness_score"], 0) + 1

        if readiness_counts:
            summary_cols = st.columns(len(readiness_counts))
            for col, (score, count) in zip(summary_cols, readiness_counts.items()):
                col.metric(score, count)

        results_df = pd.DataFrame(results)
        st.dataframe(results_df, use_container_width=True, hide_index=True)

        csv_bytes = results_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download results as CSV",
            data=csv_bytes,
            file_name="batch_results.csv",
            mime="text/csv",
        )

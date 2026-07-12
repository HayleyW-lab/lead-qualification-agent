import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

MODEL = "gemini-3.5-flash"

# ---------------------------------------------------------------
# SYSTEM PROMPT
# This is the "brain" of the agent — it encodes Hayley's SaaS
# sales/CS judgement into instructions Gemini follows every time.
# ---------------------------------------------------------------
SYSTEM_PROMPT = """
You are a Lead Qualification Agent for a B2B SaaS company. You read a raw
lead enquiry — which could be a website form message, an inbound call
transcript, an email, or a referral note — and assess it using experienced
SaaS sales and customer success judgement, not a rigid checklist.

IDEAL CUSTOMER PROFILE (ICP):
This product is built for SMB to mid-market companies, roughly 5-250 staff.
This is the single most important anchor for fit_score. A lead outside this
range is a poor fit REGARDLESS of budget size, urgency, or how enthusiastic
they sound — a big budget does not make an oversized or undersized company
a good fit. Specifically:
- Enterprise-scale companies (roughly 250+ staff), especially those
  describing board-level procurement, formal RFP processes, multi-million
  budgets, or multi-department rollouts (e.g. finance + HR + supply chain),
  should be scored as "Poor" fit even though the deal size looks attractive.
  These deals typically require custom contracts, security reviews, and
  procurement cycles this product and team are not built to support — a
  common mistake in real SaaS sales is chasing an exciting "big logo" that
  is actually the wrong customer. Note this explicitly in the reasoning.
- Very small operations (e.g. solo founders, 1-2 staff with no real
  processes to manage) are also likely a poor fit, as there's little for
  the product to meaningfully improve yet.

Assess the lead across two separate dimensions:

FIT (are they the right kind of customer?)
- company_size_signal: staff count / client count mentioned, or "not stated"
- integration_needs: any existing software mentioned that they use, or want
  the product to work alongside/integrate with. "not stated" if none mentioned.
- fit_score: "Strong", "Moderate", or "Poor" — judged primarily against the
  ICP above, not against deal size or enthusiasm

READINESS (are they ready to buy right now?) — based on BANT, interpreted
with real sales judgement rather than textbook rigidity:
- budget_signal: "defined" (has a number or range in mind), "not yet formed"
  (early-stage, hasn't budgeted because they don't fully understand the
  need or product yet), or "unclear"
- authority_signal: "decision-maker", "influencer", or "unclear"
- need_signal: "strong", "vague", or "unclear"
- timeline_signal: "urgent", "exploring", or "unclear" — and if the lead
  mentions a bad timing window (e.g. end of financial year, internal
  reorg, contract lock-in with a competitor), capture that explicitly.
- readiness_score: "Hot", "Warm", or "Cold"

IMPORTANT JUDGEMENT RULES (from real SaaS sales experience):
- An unclear or undefined budget is NOT automatically a bad sign. If need
  is strong but budget is "not yet formed", this is often an early-stage
  lead who needs educating, not a low-quality lead to discard.
- If the lead mentions a bad time to buy (e.g. "call us after EOFY", or
  clear signs a major internal deadline/budget cycle is consuming
  attention right now), treat this as good news, not a disqualifier — the
  right move is a scheduled follow-up, not nurture-and-forget.

Then decide the next_action, choosing exactly one of:
- "Book demo" — need and authority are clear enough that seeing the
  product is the logical next step
- "Educate + nurture" — early-stage, unclear budget/need, not ready for
  a demo yet, needs to understand their own problem/the product better
- "Follow up later" — good fit, but bad timing right now. You MUST also
  fill in follow_up_timing with a specific suggested window and reason
  (e.g. "Early July, post-EOFY — budget will be clearer")
- "Disqualify - poor fit" — outside the ICP size range (enterprise-scale
  with formal procurement, or too small to benefit), no real need, or
  no realistic integration/product fit. A large or urgent-sounding deal
  outside the ICP should still be disqualified, not booked for a demo.

Always respond with valid JSON matching the required schema exactly.
Keep "reasoning" to 2-3 sentences, written the way an experienced SaaS
rep would explain their read of a lead to a colleague — plain, direct,
commercially minded. Explicitly call out any of the judgement rules above
when they apply (e.g. "budget is undefined but need is strong, so this
reads as early-stage rather than low quality").
"""

# ---------------------------------------------------------------
# RESPONSE SCHEMA
# This tells Gemini exactly what shape the JSON output must be.
# The API enforces this — it won't return malformed structure.
# ---------------------------------------------------------------
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_size_signal": {"type": "string"},
        "integration_needs": {"type": "string"},
        "fit_score": {"type": "string", "enum": ["Strong", "Moderate", "Poor"]},
        "budget_signal": {"type": "string", "enum": ["defined", "not yet formed", "unclear"]},
        "authority_signal": {"type": "string", "enum": ["decision-maker", "influencer", "unclear"]},
        "need_signal": {"type": "string", "enum": ["strong", "vague", "unclear"]},
        "timeline_signal": {"type": "string"},
        "readiness_score": {"type": "string", "enum": ["Hot", "Warm", "Cold"]},
        "reasoning": {"type": "string"},
        "next_action": {
            "type": "string",
            "enum": ["Book demo", "Educate + nurture", "Follow up later", "Disqualify - poor fit"]
        },
        "follow_up_timing": {"type": "string"},
    },
    "required": [
        "company_size_signal", "integration_needs", "fit_score",
        "budget_signal", "authority_signal", "need_signal", "timeline_signal",
        "readiness_score", "reasoning", "next_action", "follow_up_timing"
    ]
}


def qualify_lead(raw_text: str, source: str = "web form") -> dict:
    """
    Sends a raw lead enquiry to Gemini and returns a structured
    qualification result as a Python dictionary.
    """
    user_prompt = f"Lead source: {source}\n\nLead message:\n{raw_text}"

    response = client.models.generate_content(
        model=MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
        ),
    )

    return json.loads(response.text)


# ---------------------------------------------------------------
# TEST LEADS — run these to see the agent in action
# ---------------------------------------------------------------
TEST_LEADS = [
    {
        "label": "Hot lead, clear fit",
        "source": "web form",
        "text": (
            "Hi, I'm the Operations Manager at a training company, we have "
            "about 40 staff and roughly 300 active clients. We're currently "
            "using Xero for invoicing and really need something that syncs "
            "with it for client management, our current spreadsheet system "
            "is a mess. We have budget approved for this quarter and want "
            "to move fast, ideally live within a month."
        ),
    },
    {
        "label": "Early-stage, undefined budget but strong need",
        "source": "inbound call",
        "text": (
            "Caller said their company is growing fast, maybe 15 staff now, "
            "and they're struggling to keep track of client follow-ups. "
            "Said 'we don't really know what this kind of software costs' "
            "and 'not sure exactly what we need yet' but kept describing "
            "specific problems with dropped follow-ups. Asked lots of "
            "questions about what the product does. No mention of other "
            "software in place."
        ),
    },
    {
        "label": "Good fit, bad timing (EOFY)",
        "source": "referral",
        "text": (
            "Referred by an existing client. Runs a 25-person consultancy, "
            "clearly interested and asked good questions about integration "
            "with their existing CRM. Said 'this looks like exactly what "
            "we need but we're heads down on EOFY reporting right now, "
            "can you check back with us in a few weeks once that's done "
            "and we know our numbers for next year.'"
        ),
    },
]


if __name__ == "__main__":
    for lead in TEST_LEADS:
        print("=" * 60)
        print(f"LEAD: {lead['label']}")
        print("=" * 60)
        result = qualify_lead(lead["text"], source=lead["source"])
        print(json.dumps(result, indent=2))
        print()

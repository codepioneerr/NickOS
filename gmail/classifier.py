"""
gmail/classifier.py
Classify emails using Claude Haiku — tuned for a CS student at Fordham.

Tiers:
  ACT_NOW     — requires action today (professor emails, deadlines, interviews, financial aid)
  OPPORTUNITY — worth reading soon (scholarships, internships, hackathons, recruiting)
  FYI         — informational, no action needed (announcements, newsletters I care about)
  JUNK        — ignore / archive (marketing, spam, irrelevant mass emails)
"""

import os
import json
import anthropic
from dotenv import load_dotenv

load_dotenv()

HAIKU_MODEL = os.environ.get("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5-20251001")

TIERS = ["ACT_NOW", "OPPORTUNITY", "FYI", "JUNK"]

SYSTEM_PROMPT = """You are an email classifier for Nick — 21-year-old CS student at Fordham University Lincoln Center (Class of 2027, Dean's List), freelance data analyst, algo trader, and sneaker reseller.

## CLASSIFICATION RULES — apply in order, stop at first match

### RULE 1 → JUNK (apply this broadly — when in doubt between FYI and JUNK, choose JUNK)
Classify as JUNK if the email is ANY of the following:
- Promotional / marketing / sales emails from ANY brand, retailer, or store (Nike, Amazon, Apple, Walmart, Target, StockX, GOAT, SNKRS, etc.)
- "Sale", "deal", "discount", "% off", "promo code", "shop now", "limited time", "exclusive offer"
- Newsletters from businesses that are essentially marketing (even if Nick subscribed)
- Social media activity notifications (LinkedIn connection/like/comment, Instagram, Twitter, Facebook)
- Automated digest emails from apps (Daily digest, weekly summary from non-essential services)
- Cold outreach / spam that is not relevant to CS, finance, or Fordham
- Subscription confirmation or unsubscribe emails
- Rewards/points/loyalty program emails

### RULE 2 → ACT_NOW (requires action within 24–48 hours)
Classify as ACT_NOW if from or about:
- Any @fordham.edu sender who is faculty, staff, financial aid, registrar, bursar, or dean
- Scholarship application deadlines or status updates
- Interview invitations or scheduling requests (any company)
- Internship/job offer letters or hiring team follow-ups
- Upwork direct client messages or contract offers
- Study abroad office (London Fall 2026 appeal specifically)
- Bank fraud alerts, security alerts requiring action
- Subject contains: "deadline", "action required", "expires", "respond by", "urgent", "offer expires"

### RULE 3 → OPPORTUNITY (worth reading within 1–3 days, no urgent deadline)
Classify as OPPORTUNITY if:
- New scholarship announcements (no imminent deadline)
- Hackathon invitations (MLH, university-sponsored, tech company)
- Recruiting/sourcing emails from tech or finance companies
- Career fair, networking event, or info session invitations
- Fordham CS department events, speaker series, club announcements
- Upwork job match notifications or profile views
- GitHub notifications about your own repos (PR reviews, issues mentioning you)
- Broker/trading platform alerts about account activity (not promotional)

### RULE 4 → FYI (genuinely useful info, no action needed, not marketing)
FYI is ONLY for transactional or informational emails with real utility:
- Order confirmations and shipping/delivery notifications (packages, not promo)
- Bank or credit card statements and transaction alerts (not fraud)
- GitHub CI/CD status, Dependabot, automated security alerts on your repos
- Fordham system notifications (grade posted, registration confirmation, class cancellation)
- Password reset or account security emails (informational, no threat)
- Receipts from services Nick actively uses (Spotify, AWS, Vercel, Railway, etc.)
- Direct replies from real humans that are purely informational with no action needed

## IMPORTANT
- If unsure between JUNK and FYI → choose JUNK
- If unsure between FYI and OPPORTUNITY → choose OPPORTUNITY
- Never put promotional/marketing emails in FYI

## OUTPUT FORMAT
Respond with ONLY a raw JSON array — no markdown, no code fences, no explanation.
Each element: {"id": "<id>", "tier": "<TIER>", "reason": "<one crisp sentence max 10 words>"}"""


def classify_emails(emails: list[dict]) -> list[dict]:
    """
    Classify a list of email dicts via Claude Haiku.
    Input:  list of {id, sender, sender_email, subject, snippet}
    Output: list of {id, tier, reason}
    """
    if not emails:
        return []

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Build compact representation for the model — no need to send full bodies
    email_list = [
        {
            "id":           e["id"],
            "from":         f"{e['sender']} <{e['sender_email']}>",
            "subject":      e["subject"],
            "preview":      e["snippet"][:200],   # first 200 chars of snippet
        }
        for e in emails
    ]

    user_msg = f"Classify these {len(email_list)} emails:\n\n{json.dumps(email_list, indent=2)}"

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=2048,
        temperature=0,        # deterministic — same inbox → same classification
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )

    raw = response.content[0].text.strip()

    # Parse — be tolerant of minor formatting issues
    try:
        results = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON array if model added stray text
        import re
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            results = json.loads(m.group())
        else:
            # Fallback: mark everything FYI so nothing is lost
            results = [{"id": e["id"], "tier": "FYI", "reason": "classifier error"} for e in emails]

    # Validate tiers
    for r in results:
        if r.get("tier") not in TIERS:
            r["tier"] = "FYI"

    return results


def merge_classifications(emails: list[dict], classifications: list[dict]) -> list[dict]:
    """
    Merge classification results back into email dicts.
    Returns enriched emails with 'tier' and 'reason' fields added.
    """
    class_map = {c["id"]: c for c in classifications}
    enriched = []
    for e in emails:
        c = class_map.get(e["id"], {"tier": "FYI", "reason": "unclassified"})
        enriched.append({**e, "tier": c["tier"], "reason": c.get("reason", "")})
    return enriched


def group_by_tier(enriched_emails: list[dict]) -> dict[str, list[dict]]:
    """Group enriched emails by tier. Returns dict with all 4 tiers as keys."""
    groups = {t: [] for t in TIERS}
    for e in enriched_emails:
        groups[e["tier"]].append(e)
    return groups

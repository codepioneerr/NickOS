"""
bot/handlers/email.py
Command: /email
Fetches all 4 Gmail accounts, classifies via Claude Haiku, applies labels,
and sends one consolidated Telegram digest.
"""

from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.utils import ET, today_label, append_daily_log

TIER_CONFIG = {
    "ACT_NOW":     {"emoji": "🔴", "label": "ACT NOW",     "show_reasons": True},
    "OPPORTUNITY": {"emoji": "🟡", "label": "OPPORTUNITY", "show_reasons": True},
    "FYI":         {"emoji": "📋", "label": "FYI",         "show_reasons": False},
    "JUNK":        {"emoji": "🗑",  "label": "JUNK",        "show_reasons": False},
}

MAX_SHOWN_PER_TIER = 6   # across all accounts combined


async def email_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /email        — triage all accounts, last 24h
    /email 48     — look back 48h
    """
    hours_back = 24
    if context.args:
        try:
            hours_back = int(context.args[0])
        except ValueError:
            pass

    status_msg = await update.message.reply_text(
        f"📬 <b>Checking all inboxes...</b>\n<i>Fetching last {hours_back}h across all accounts</i>",
        parse_mode=ParseMode.HTML
    )

    try:
        from gmail.fetcher import fetch_all_accounts, load_accounts
        from gmail.classifier import classify_emails, merge_classifications, group_by_tier
        from gmail.labels import ensure_labels_exist, apply_labels_to_emails

        # ── 1. Check at least one account is configured ───────────────────────
        accounts = load_accounts()
        if not accounts:
            await status_msg.edit_text(
                "❌ <b>No Gmail accounts configured.</b>\n\n"
                "Add to <code>.env</code>:\n"
                "<code>GMAIL_ACCOUNT_1_EMAIL=you@gmail.com</code>\n"
                "<code>GMAIL_ACCOUNT_1_NAME=Main</code>\n\n"
                "Then run:\n"
                "<code>python scripts/setup_gmail_oauth.py --account 1</code>",
                parse_mode=ParseMode.HTML
            )
            return

        # ── 2. Fetch all accounts ─────────────────────────────────────────────
        all_emails, fetch_errors = fetch_all_accounts(
            max_per_account=50, hours_back=hours_back
        )

        configured_count = len(accounts)
        failed_count     = len(fetch_errors)
        ok_count         = configured_count - failed_count

        if not all_emails and fetch_errors:
            # Every account failed — likely none are authorized
            error_lines = "\n".join(
                f"• {e['account']['name']}: {e['error'][:80]}"
                for e in fetch_errors
            )
            await status_msg.edit_text(
                "❌ <b>All accounts failed to fetch.</b>\n\n"
                f"<code>{error_lines}</code>\n\n"
                "Run: <code>python scripts/setup_gmail_oauth.py --account N</code>",
                parse_mode=ParseMode.HTML
            )
            return

        if not all_emails:
            accounts_str = ", ".join(a["name"] for a in accounts if
                                     not any(e["account"]["index"] == a["index"] for e in fetch_errors))
            await status_msg.edit_text(
                f"📭 <b>All clear!</b>\n"
                f"<i>No unread emails in the last {hours_back}h across {ok_count} account(s).</i>",
                parse_mode=ParseMode.HTML
            )
            return

        await status_msg.edit_text(
            f"📬 <b>Classifying {len(all_emails)} emails...</b>\n"
            f"<i>Claude Haiku across {ok_count}/{configured_count} accounts</i>",
            parse_mode=ParseMode.HTML
        )

        # ── 3. Classify all emails in one Haiku call ──────────────────────────
        classifications = classify_emails(all_emails)
        enriched        = merge_classifications(all_emails, classifications)
        groups          = group_by_tier(enriched)

        # ── 4. Apply labels per account ───────────────────────────────────────
        # Group enriched emails by account so we only call ensure_labels_exist once per account
        from collections import defaultdict
        by_account: dict[int, list] = defaultdict(list)
        for e in enriched:
            by_account[e["account_index"]].append(e)

        from gmail.fetcher import get_service_for_account
        for account in accounts:
            acc_emails = by_account.get(account["index"], [])
            if not acc_emails:
                continue
            try:
                svc           = get_service_for_account(account)
                tier_to_label = ensure_labels_exist(svc)
                apply_labels_to_emails(svc, acc_emails, tier_to_label)
            except Exception:
                pass  # non-fatal

        # ── 5. Build consolidated digest ──────────────────────────────────────
        digest = _build_digest(groups, hours_back, accounts, fetch_errors)
        await status_msg.edit_text(digest, parse_mode=ParseMode.HTML)

        # ── 6. Daily log ──────────────────────────────────────────────────────
        append_daily_log(
            "Notes",
            f"Email triage: {len(all_emails)} emails across {ok_count} accounts — "
            f"{len(groups['ACT_NOW'])} Act Now, {len(groups['OPPORTUNITY'])} Opportunity "
            f"({datetime.now(ET).strftime('%H:%M ET')})"
        )

    except Exception as e:
        await status_msg.edit_text(
            f"❌ <b>Triage error:</b>\n<code>{str(e)[:300]}</code>",
            parse_mode=ParseMode.HTML
        )


def _build_digest(
    groups: dict,
    hours_back: int,
    accounts: list,
    fetch_errors: list,
) -> str:
    label = today_label()
    total = sum(len(v) for v in groups.values())

    ok_names   = [a["name"] for a in accounts
                  if not any(e["account"]["index"] == a["index"] for e in fetch_errors)]
    fail_names = [e["account"]["name"] for e in fetch_errors]

    account_summary = " · ".join(ok_names)
    lines = [
        f"📬 <b>Inbox Triage — {label}</b>",
        f"<i>{total} unread · {len(ok_names)} accounts: {account_summary}</i>",
    ]
    if fail_names:
        lines.append(f"<i>⚠️ Skipped (not authorized): {', '.join(fail_names)}</i>")
    lines.append("")

    for tier in ["ACT_NOW", "OPPORTUNITY", "FYI", "JUNK"]:
        emails = groups[tier]
        cfg    = TIER_CONFIG[tier]
        count  = len(emails)
        if count == 0:
            continue

        lines.append(f"{cfg['emoji']} <b>{cfg['label']} ({count})</b>")

        if tier == "JUNK":
            lines.append("  <i>Labeled in Gmail.</i>")
        elif tier == "FYI" and count > MAX_SHOWN_PER_TIER:
            for i, e in enumerate(emails[:3], 1):
                lines.append(f"  {i}. {_fmt(e)}")
            lines.append(f"  <i>...and {count - 3} more</i>")
        else:
            for i, e in enumerate(emails[:MAX_SHOWN_PER_TIER], 1):
                line = f"  {i}. {_fmt(e)}"
                if cfg["show_reasons"] and e.get("reason"):
                    line += f"\n      <i>{e['reason']}</i>"
                lines.append(line)
            if count > MAX_SHOWN_PER_TIER:
                lines.append(f"  <i>...and {count - MAX_SHOWN_PER_TIER} more</i>")

        lines.append("")

    act_now = len(groups["ACT_NOW"])
    lines.append(
        f"⚡ <b>{act_now} email(s) need action today.</b>"
        if act_now else
        "✅ <i>Nothing urgent across all accounts.</i>"
    )
    lines.append(f"<i>Labels applied · /email 48 for wider window</i>")
    return "\n".join(lines)


def _fmt(email: dict) -> str:
    """One-line format with account tag: [Main] Sender — Subject"""
    acct    = email.get("account_name", "")
    sender  = email.get("sender") or email.get("sender_email", "?")
    subject = email.get("subject", "(no subject)")
    if len(sender)  > 22: sender  = sender[:19]  + "..."
    if len(subject) > 40: subject = subject[:37] + "..."
    tag = f"[{acct}] " if acct else ""
    return f"{tag}<b>{sender}</b> — {subject}"

"""
gmail/labels.py
Manage NickOS Gmail labels and apply them after classification.
"""

from googleapiclient.errors import HttpError

# Label definitions — name visible in Gmail, color for visual scanning
NICKOS_LABELS = {
    "ACT_NOW":     {"name": "NickOS/ActNow",     "color": {"backgroundColor": "#cc0000", "textColor": "#ffffff"}},
    "OPPORTUNITY": {"name": "NickOS/Opportunity", "color": {"backgroundColor": "#ff9900", "textColor": "#ffffff"}},
    "FYI":         {"name": "NickOS/FYI",         "color": {"backgroundColor": "#1a73e8", "textColor": "#ffffff"}},
    "JUNK":        {"name": "NickOS/Junk",        "color": {"backgroundColor": "#999999", "textColor": "#ffffff"}},
}


def ensure_labels_exist(service) -> dict[str, str]:
    """
    Create NickOS labels in Gmail if they don't exist.
    Returns a dict mapping tier → label_id.
    """
    existing = service.users().labels().list(userId="me").execute().get("labels", [])
    existing_map = {l["name"]: l["id"] for l in existing}

    tier_to_label_id = {}
    for tier, config in NICKOS_LABELS.items():
        label_name = config["name"]
        if label_name in existing_map:
            tier_to_label_id[tier] = existing_map[label_name]
        else:
            try:
                new_label = service.users().labels().create(
                    userId="me",
                    body={
                        "name": label_name,
                        "messageListVisibility": "show",
                        "labelListVisibility": "labelShow",
                        "color": config["color"],
                    }
                ).execute()
                tier_to_label_id[tier] = new_label["id"]
                print(f"  Created Gmail label: {label_name}")
            except HttpError as e:
                print(f"  ⚠️  Could not create label {label_name}: {e}")

    return tier_to_label_id


def apply_label(service, message_id: str, label_id: str):
    """Apply a label to a message."""
    try:
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"addLabelIds": [label_id]}
        ).execute()
    except HttpError as e:
        print(f"  ⚠️  Could not apply label to {message_id}: {e}")


def apply_labels_to_emails(service, enriched_emails: list[dict], tier_to_label_id: dict[str, str]):
    """Bulk-apply NickOS labels to all classified emails."""
    for email in enriched_emails:
        tier     = email.get("tier", "FYI")
        label_id = tier_to_label_id.get(tier)
        if label_id:
            apply_label(service, email["id"], label_id)

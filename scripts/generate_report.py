import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "reports"

INPUT_FILE = REPORT_DIR / "incidents.json"
CSV_FILE = REPORT_DIR / "incidents.csv"
SUMMARY_FILE = REPORT_DIR / "incident-summary.json"

IST = ZoneInfo("Asia/Kolkata")

PRIORITY_LABELS = {
    "1": "P1 - Critical",
    "2": "P2 - High",
    "3": "P3 - Moderate",
    "4": "P4 - Low",
    "5": "P5 - Planning",
}

STATE_LABELS = {
    "1": "New",
    "2": "In Progress",
    "3": "On Hold",
    "6": "Resolved",
    "7": "Closed",
    "8": "Canceled",
}

CSV_FIELDS = [
    "number",
    "priority",
    "state",
    "assigned_to",
    "assignment_group",
    "short_description",
    "description",
    "work_notes",
    "sys_created_on",
    "sys_updated_on",
    "sys_id",
]


def normalize_priority(value):
    value = str(value or "").strip()

    if value in PRIORITY_LABELS:
        return PRIORITY_LABELS[value]

    # Accommodate display values such as "1 - Critical".
    for number, label in PRIORITY_LABELS.items():
        if value == label or value.startswith(number + " -"):
            return label

    return value or "Unknown"


def normalize_state(value):
    value = str(value or "").strip()

    if value in STATE_LABELS:
        return STATE_LABELS[value]

    # Accommodate display values such as "In Progress".
    for label in STATE_LABELS.values():
        if value.casefold() == label.casefold():
            return label

    return value or "Unknown"


def flatten_work_notes(notes):
    """Flatten note objects for CSV output."""
    if not isinstance(notes, list):
        return ""

    lines = []

    for item in notes:
        if not isinstance(item, dict):
            continue

        note = str(item.get("note", "")).strip()
        created_at = str(item.get("created_at", "")).strip()
        created_by = str(item.get("created_by", "")).strip()

        if not note:
            continue

        lines.append(
            f"[{created_at} by {created_by}] {note}"
        )

    return "\n".join(lines)


def load_incidents():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Incident input file not found: {INPUT_FILE}"
        )

    with INPUT_FILE.open("r", encoding="utf-8") as file:
        incidents = json.load(file)

    if not isinstance(incidents, list):
        raise ValueError("Incident JSON must contain a list.")

    for incident in incidents:
        incident["priority"] = normalize_priority(
            incident.get("priority")
        )
        incident["state"] = normalize_state(
            incident.get("state")
        )

        incident["assigned_to"] = (
            incident.get("assigned_to") or "Unassigned"
        )
        incident["assignment_group"] = (
            incident.get("assignment_group") or "Unassigned"
        )
        incident["work_notes"] = (
            incident.get("work_notes")
            if isinstance(incident.get("work_notes"), list)
            else []
        )

    return incidents


def create_summary(incidents):
    priority_counts = Counter(
        incident["priority"] for incident in incidents
    )
    state_counts = Counter(
        incident["state"] for incident in incidents
    )

    report_time = datetime.now(IST).isoformat(timespec="seconds")

    return {
        "report_time": report_time,
        "timezone": "Asia/Kolkata",
        "total_incidents": len(incidents),
        "priority_counts": dict(priority_counts),
        "state_counts": dict(state_counts),
    }


def write_csv(incidents):
    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()

        for incident in incidents:
            row = dict(incident)
            row["work_notes"] = flatten_work_notes(
                incident.get("work_notes", [])
            )
            writer.writerow(row)


def write_json(incidents):
    with INPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            incidents,
            file,
            indent=2,
            ensure_ascii=False,
        )


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        incidents = load_incidents()
        summary = create_summary(incidents)

        write_csv(incidents)
        write_json(incidents)

        with SUMMARY_FILE.open("w", encoding="utf-8") as file:
            json.dump(summary, file, indent=2, ensure_ascii=False)

        print(f"Total incidents: {summary['total_incidents']}")
        print(f"CSV report: {CSV_FILE}")
        print(f"JSON report: {INPUT_FILE}")
        print(f"Summary report: {SUMMARY_FILE}")

    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: Report generation failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

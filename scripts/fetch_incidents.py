import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException


BASE_DIR = Path(__file__).resolve().parent.parent
REPORT_DIR = BASE_DIR / "reports"
OUTPUT_FILE = REPORT_DIR / "incidents.json"

INCIDENT_FIELDS = [
    "sys_id",
    "number",
    "short_description",
    "description",
    "priority",
    "state",
    "assigned_to",
    "assignment_group",
    "sys_created_on",
    "sys_updated_on",
]

JOURNAL_FIELDS = [
    "element_id",
    "element",
    "value",
    "sys_created_on",
    "sys_created_by",
]

PAGE_SIZE = int(os.getenv("SERVICENOW_PAGE_SIZE", "1000"))
MAX_RETRIES = 3
WORK_NOTES_PER_INCIDENT = 3


def get_config():
    """Load and validate the ServiceNow connection settings."""
    instance = os.getenv("SERVICENOW_INSTANCE", "").strip().rstrip("/")
    username = os.getenv("SERVICENOW_USERNAME", "")
    password = os.getenv("SERVICENOW_PASSWORD", "")

    if not instance or not username or not password:
        raise ValueError(
            "SERVICENOW_INSTANCE, SERVICENOW_USERNAME, "
            "and SERVICENOW_PASSWORD must be configured."
        )

    if not instance.startswith("https://"):
        instance = f"https://{instance}"

    return instance, username, password


def normalize_instance_value(value):
    """
    Convert ServiceNow reference/display-value objects to readable strings.
    """
    if isinstance(value, dict):
        return value.get("display_value") or value.get("value") or ""

    if value is None:
        return ""

    return str(value)


def api_get(session, url, params):
    """Perform a GET request with basic retry handling."""
    for attempt in range(MAX_RETRIES):
        try:
            response = session.get(
                url,
                params=params,
                timeout=(10, 60),
            )

            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < MAX_RETRIES - 1:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = min(int(retry_after), 30) if retry_after else 2 ** attempt
                    except ValueError:
                        delay = 2 ** attempt

                    time.sleep(delay)
                    continue

            response.raise_for_status()
            return response.json()

        except RequestException:
            if attempt == MAX_RETRIES - 1:
                raise

            time.sleep(2 ** attempt)

    raise RuntimeError("ServiceNow request failed after retries.")


def create_session(username, password):
    """Create an HTTP session for the ServiceNow API."""
    session = requests.Session()
    session.auth = HTTPBasicAuth(username, password)
    session.headers.update({
        "Accept": "application/json",
        "User-Agent": "servicenow-incident-reporting/1.0",
    })
    return session


def fetch_incidents(session, instance):
    """Fetch incident records with pagination."""
    endpoint = f"{instance}/api/now/table/incident"

    query = os.getenv("SERVICENOW_QUERY", "").strip()

    incidents = []
    offset = 0

    while True:
        params = {
            "sysparm_fields": ",".join(INCIDENT_FIELDS),
            "sysparm_display_value": "all",
            "sysparm_exclude_reference_link": "true",
            "sysparm_limit": PAGE_SIZE,
            "sysparm_offset": offset,
            "sysparm_orderby": "sys_updated_on",
        }

        if query:
            params["sysparm_query"] = query

        payload = api_get(session, endpoint, params)
        results = payload.get("result", [])

        if not isinstance(results, list):
            raise ValueError("Unexpected response from ServiceNow Incident API.")

        if not results:
            break

        for item in results:
            incident = {
                field: normalize_instance_value(item.get(field))
                for field in INCIDENT_FIELDS
            }

            incidents.append(incident)

        print(
            f"Fetched {len(results)} incidents; "
            f"total collected: {len(incidents)}"
        )

        if len(results) < PAGE_SIZE:
            break

        offset += len(results)

    return incidents


def fetch_work_notes(session, instance, incidents):
    """
    Fetch recent work notes from sys_journal_field.

    Requires the integration user to have read access to the relevant
    journal records. Work notes are not returned by the incident Table API.
    """
    endpoint = f"{instance}/api/now/table/sys_journal_field"

    sys_ids = [
        incident["sys_id"]
        for incident in incidents
        if incident.get("sys_id")
    ]

    notes_by_incident = defaultdict(list)

    # Keep encoded queries manageable by using batches.
    batch_size = 50

    for start in range(0, len(sys_ids), batch_size):
        batch = sys_ids[start:start + batch_size]
        encoded_ids = ",".join(batch)

        params = {
            "sysparm_query": (
                "name=incident"
                "^element=work_notes"
                f"^element_idIN{encoded_ids}"
                "^ORDERBYDESCsys_created_on"
            ),
            "sysparm_fields": ",".join(JOURNAL_FIELDS),
            "sysparm_display_value": "false",
            "sysparm_limit": "1000",
        }

        payload = api_get(session, endpoint, params)

        for note in payload.get("result", []):
            incident_id = note.get("element_id")

            if not incident_id:
                continue

            notes_by_incident[incident_id].append({
                "created_at": note.get("sys_created_on", ""),
                "created_by": note.get("sys_created_by", ""),
                "note": note.get("value", ""),
            })

    # The API returns the newest notes first. Keep the three newest.
    for incident in incidents:
        incident_id = incident.get("sys_id", "")
        incident_notes = notes_by_incident.get(incident_id, [])

        incident["work_notes"] = incident_notes[:WORK_NOTES_PER_INCIDENT]

    return incidents


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        instance, username, password = get_config()

        with create_session(username, password) as session:
            incidents = fetch_incidents(session, instance)

            if incidents:
                incidents = fetch_work_notes(
                    session,
                    instance,
                    incidents,
                )
            else:
                print("No incidents were returned.")

        with OUTPUT_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                incidents,
                file,
                indent=2,
                ensure_ascii=False,
            )

        print(f"Saved {len(incidents)} incidents to {OUTPUT_FILE}")

    except (ValueError, RequestException, RuntimeError) as exc:
        print(f"ERROR: Incident collection failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

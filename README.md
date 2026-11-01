# ServiceNow Incident Reporting

Automatically collect ServiceNow incidents, generate CSV and JSON
reports, and send an incident status report to Microsoft Teams.

## Features

- Scheduled reports at 09:00 AM and 05:00 PM IST.
- Manual execution through GitHub Actions.
- ServiceNow Incident Table API integration.
- Optional collection of incident work notes.
- Incident counts grouped by priority and state.
- CSV and JSON reports.
- Microsoft Teams webhook notification.
- GitHub Actions artifact storage.

## Architecture

ServiceNow REST API
        |
        v
GitHub Actions
        |
        v
Fetch Incidents and Work Notes
        |
        v
Generate CSV and JSON Reports
        |
        v
Teams Workflows Webhook
        |
        v
Microsoft Teams Channel

## Requirements

- GitHub repository
- ServiceNow instance with API access
- Read-only ServiceNow integration account
- Microsoft Teams channel
- Teams Workflows webhook
- Python 3.12

## GitHub Secrets

Open:

Repository Settings
  -> Secrets and variables
  -> Actions
  -> New repository secret

Configure:

SERVICENOW_INSTANCE
SERVICENOW_USERNAME
SERVICENOW_PASSWORD
TEAMS_WEBHOOK_URL

SERVICENOW_INSTANCE example:

company.service-now.com

Do not include credentials in the repository.

## Optional Repository Variable

Open:

Settings
  -> Secrets and variables
  -> Actions
  -> Variables

Create:

SERVICENOW_QUERY

Leave it empty to request all incidents accessible to the integration
account. Configure a ServiceNow encoded query if only a particular
incident population should be reported.

For example, use a validated query appropriate to your instance to
restrict the report to a particular assignment group or time period.

## Local Setup

Create a virtual environment:

python3 -m venv .venv

Activate it on macOS or Linux:

source .venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Set the required environment variables securely.

Run the collection step:

python scripts/fetch_incidents.py

Generate reports:

python scripts/generate_report.py

Send the report:

python scripts/send_teams_report.py

## Run Tests

python -m unittest discover -s tests -v

## GitHub Actions

Open:

Repository
  -> Actions
  -> ServiceNow Incident Status Report
  -> Run workflow

The workflow also runs on its configured schedule.

## Generated Reports

reports/incidents.csv
reports/incidents.json
reports/incident-summary.json

Reports are uploaded as GitHub Actions artifacts for seven days.

Repository access and artifact access should be restricted because
incident descriptions and work notes can contain sensitive data.

## Security

- Use a dedicated integration account.
- Grant only the required read permissions.
- Prefer OAuth 2.0 where supported.
- Store credentials in GitHub Actions secrets.
- Never print credentials or webhook URLs in logs.
- Restrict repository and artifact access.
- Follow company data retention requirements.
- Validate ServiceNow table and journal ACLs.
- Validate the Teams workflow payload schema.

## Limitations

ServiceNow state values and display values may vary by instance.
Validate priority and state mappings before production use.

The journal API may restrict work-note access.

The Teams workflow must be configured to accept the JSON payload
sent by the reporting script.

Scheduled GitHub Actions execution is not guaranteed to start
at the exact scheduled minute.

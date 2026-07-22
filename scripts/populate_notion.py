import os
import requests
from dotenv import load_dotenv

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

NOTION_VERSION = "2022-06-28"
HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION,
}

TICKETS = [
    {
        "id": "DEV-001",
        "name": "Project Initialization & Core Documentation",
        "domain": "DevOps",
        "priority": "High",
        "type": "Task",
        "description": (
            "Create the mandatory folder structure: ui, backend, database, secrets, "
            "images, docs, and tests. Inside the docs folder, initialize "
            "problemStatement.md, architecture.md, context.md, "
            "Implementation_plan.md, edge_case.md, and deployment.md."
        ),
        "acceptance_criteria": (
            "1. Folders and markdown files exist. "
            "2. problemStatement.md is populated with the initial project context. "
            "3. context.md is updated."
        ),
    },
    {
        "id": "ENG-002",
        "name": "Phase 1 - Data Gathering & Cleaning Script",
        "domain": "Data Engineering",
        "priority": "High",
        "type": "Task",
        "description": (
            "Write a Python script to collect public feedback from app reviews, "
            "Reddit, and forums. Store inputs with source, date, platform, category, "
            "intent, and text. Clean the data by removing duplicates/spam and "
            "normalizing comments."
        ),
        "acceptance_criteria": (
            "1. Script successfully gathers and cleans data. "
            "2. Output saved locally for AI processing. "
            "3. Tests added to the tests folder. "
            "4. context.md updated."
        ),
    },
    {
        "id": "AI-003",
        "name": "Phase 1 - Groq AI Analysis & Theme Extraction",
        "domain": "AI",
        "priority": "High",
        "type": "Task",
        "description": (
            "Use Groq AI to review the cleaned dataset. Classify comments by "
            "sentiment, theme, blocker, and trigger. The AI must quote supporting "
            "evidence for every theme. Generate structured insights formatting "
            "observation, user need, root cause, opportunity, and implication."
        ),
        "acceptance_criteria": (
            "1. Groq API successfully processes data. "
            "2. Themes are identified by frequency and consistency. "
            "3. Findings logged in docs. "
            "4. context.md updated."
        ),
    },
    {
        "id": "OPS-004",
        "name": "Phase 1 - User Research Automation Workflow",
        "domain": "Operations",
        "priority": "Medium",
        "type": "Task",
        "description": (
            "Set up an automated workflow to validate AI insights. Create a "
            "Google Form/Typeform for screening. Use n8n/Zapier to route eligible "
            "respondents to a tracker (Sheets/Airtable). Configure Groq AI to "
            "summarize responses and match them against Phase 1 AI discovery themes "
            "to generate an insight quality score."
        ),
        "acceptance_criteria": (
            "1. Automation workflow is fully functional. "
            "2. Mock data passes through the webhook/Zapier into the tracker. "
            "3. Summarization works."
        ),
    },
    {
        "id": "DB-005",
        "name": "Phase 2 - PostgreSQL Database Setup",
        "domain": "Database",
        "priority": "High",
        "type": "Task",
        "description": (
            "Set up PostgreSQL as the primary database. Create schemas and tables "
            "for: users, products, categories, recommendations, feedback, tickets, "
            "test data, and workflow outputs."
        ),
        "acceptance_criteria": (
            "1. PostgreSQL instance running locally. "
            "2. Schemas created and mock data seeded. "
            "3. Credentials securely stored in the secrets folder."
        ),
    },
    {
        "id": "ENG-006",
        "name": 'Phase 2 - "Try Next Basket" Backend Logic',
        "domain": "Backend",
        "priority": "High",
        "type": "Task",
        "description": (
            "Build the MVP Python backend. Create an endpoint that evaluates a "
            "user's cart/history, uses Groq AI to identify adjacent categories, "
            'and returns a "starter bundle" recommendation with a generated '
            "rationale explaining why it is relevant."
        ),
        "acceptance_criteria": (
            "1. Endpoint is functional, communicates with Groq AI, interacts with "
            "PostgreSQL for product data, and returns proper JSON payload. "
            "2. Validated via the tests folder."
        ),
    },
    {
        "id": "UI-007",
        "name": "Phase 2 - Develop MVP Web Interface",
        "domain": "Frontend",
        "priority": "High",
        "type": "Task",
        "description": (
            "Review the UI screenshots in the images folder. Build a lightweight "
            "frontend that connects to the backend API. Display the current cart "
            "and the AI-generated starter bundle recommendation, along with "
            '"Add to Cart" or "Not Interested" feedback buttons.'
        ),
        "acceptance_criteria": (
            "1. UI matches reference images. "
            "2. Successfully calls the backend API and logs user feedback into "
            "the PostgreSQL database."
        ),
    },
    {
        "id": "DEV-008",
        "name": "Phase 2 - Railway Deployment & Final QA",
        "domain": "DevOps",
        "priority": "High",
        "type": "Task",
        "description": (
            "Deploy the Python backend, UI, and PostgreSQL database to Railway. "
            "Document the setup, environment variables, and commands in "
            "docs/deployment.md. Run final end-to-end testing."
        ),
        "acceptance_criteria": (
            "1. MVP is live on Railway. "
            "2. deployment.md is complete. "
            "3. Final update made to context.md for PPT presentation readiness."
        ),
    },
]


def rich_text(text):
    return [{"type": "text", "text": {"content": text}}]


def create_ticket(ticket):
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "Ticket Name": {
                "title": rich_text(ticket["name"])
            },
            "Domain": {
                "select": {"name": ticket["domain"]}
            },
            "Priority": {
                "select": {"name": ticket["priority"]}
            },
            "Status": {
                "status": {"name": "To Do"}
            },
            "Ticket ID": {
                "rich_text": rich_text(ticket["id"])
            },
            "Ticket Type": {
                "select": {"name": ticket["type"]}
            },
        },
        "children": [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "Description"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": rich_text(ticket["description"])
                },
            },
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "Acceptance Criteria"}}
                    ]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": rich_text(ticket["acceptance_criteria"])
                },
            },
        ],
    }

    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers=HEADERS,
        json=payload,
    )

    if resp.status_code == 200:
        print(f"Created: {ticket['id']} - {ticket['name']}")
    else:
        print(f"Failed: {ticket['id']} | {resp.status_code} | {resp.text}")


if __name__ == "__main__":
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise SystemExit(
            "Missing NOTION_API_KEY or NOTION_DATABASE_ID in .env"
        )

    for ticket in TICKETS:
        create_ticket(ticket)

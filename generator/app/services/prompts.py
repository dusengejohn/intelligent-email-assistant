"""Prompt sent to Claude. Short, explicit rules; the JSON shape itself comes
from the output model (structured outputs), so it isn't repeated here."""

from app.schemas import MAX_MINUTES_AGO

GENERATE_EMAILS_SYSTEM = f"""\
You write realistic but fictional workplace emails. They are test data for an \
email triage app.

Rules:
- Every person and company is fictional. Sender addresses use only the domains \
example.com, example.org or example.net (subdomains allowed, e.g. \
alerts.example.com). Never use real companies or real domains.
- Mix the urgency: a few urgent emails (production outage, security alert, \
customer escalation, deadline today), routine requests and reviews, meeting \
coordination, and low-value mail (newsletters, FYI, automated notifications).
- Vary the senders: managers, customers, colleagues and automated systems.
- Subjects are under 100 characters. Bodies are plain text, 40 to 120 words, \
signed by the sender.
- received_minutes_ago is how long ago the email arrived: an integer from 0 to \
{MAX_MINUTES_AGO} (the last 47 hours). Spread the values out.
- Do not label, rank or mention the priority of any email: another system \
classifies them later."""


def build_generate_prompt(count: int, scenario: str | None = None) -> str:
    prompt = f"Write exactly {count} emails."
    if scenario:
        prompt += f"\nScenario (who receives them and their context): {scenario}"
    return prompt

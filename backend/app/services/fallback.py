"""Rule-based priority classifier: no AI, no network, always available.

Used when Claude isn't configured, fails, or returns invalid output (story 2.2).
The rules are an ORDERED table: the first rule that matches decides, so more
urgent rules come first. Order (see RULES below):

  1. critical words  (outage, breach, legal, deadline today, exec escalation, ...)
  2. clear low markers (newsletter, digest, FYI, ...) - before "high", so a
     newsletter that mentions customers stays low
  3. high words      (customer, blocked, tomorrow, ASAP, escalation, ...)
  4. automated sender (noreply@, alerts@, ...) -> low
  5. nothing matched -> moderate (a normal work request)
"""

import re
from dataclasses import dataclass

from app.models import ClassificationSource, Email, Priority
from app.priorities import default_minutes
from app.schemas import Classification


def words(*patterns: str) -> re.Pattern[str]:
    """Match any pattern as whole words/phrases, ignoring case.

    `\\b` = word boundary, so "down" matches "is down" but not "download".
    """
    return re.compile(r"\b(?:" + "|".join(patterns) + r")\b", re.IGNORECASE)


@dataclass(frozen=True)
class Rule:
    priority: Priority
    signal: str  # what the rule means, used in the reason sentence
    pattern: re.Pattern[str]
    # Optional second condition that must ALSO match (e.g. escalation + executive)
    also: re.Pattern[str] | None = None


C, H, L = Priority.CRITICAL, Priority.HIGH, Priority.LOW

RULES: list[Rule] = [
    # 1. critical
    Rule(C, "an outage", words(r"outages?")),
    Rule(
        C,
        "a service that is down",
        # "the database is down", "production DOWN" - but not "slow down"
        words(
            r"(?:production|prod|database|db|site|website|server|service|system|api|app|network)s?"
            r"\s+(?:is\s+|are\s+|went\s+|has\s+gone\s+)?down"
        ),
    ),
    Rule(
        C,
        "a service failing",
        # "errors spiking", "API degraded", "login service unavailable"
        words(
            r"errors?\s+(?:are\s+|is\s+)?spiking",
            r"error rate",
            r"degraded",
            r"(?:service|site|website|api|checkout|payments?|login)s?\s+(?:is\s+|are\s+)?"
            r"(?:unavailable|unreachable)",
        ),
    ),
    Rule(
        C,
        "a security incident",
        words(
            r"breach(?:ed)?",
            r"security incident",
            r"ransomware",
            r"malware",
            r"phishing",
            r"data loss",
            r"compromised",
            r"unauthori[sz]ed",
            # "suspicious login attempts", "unusual admin sign-in" - not "unusual request"
            r"(?:suspicious|unusual)\s+(?:admin\s+)?(?:logins?|sign-?ins?|activity|access)",
        ),
    ),
    Rule(
        C,
        "a legal or compliance matter",
        words(r"legal", r"lawsuit", r"compliance", r"regulators?", r"regulatory", r"subpoena"),
    ),
    Rule(
        C,
        "an executive escalation",
        words(r"escalat\w*"),
        also=words(r"ceo", r"cto", r"cfo", r"coo", r"vp", r"vice president", r"executives?"),
    ),
    Rule(
        C,
        "a deadline today",
        words(r"due today", r"deadline today", r"by end of (?:the )?day", r"eod", r"tonight"),
    ),
    # 2. clear low markers (before "high", see module docstring)
    Rule(
        L,
        "a newsletter or FYI",
        words(r"newsletter", r"digest", r"unsubscribe", r"fyi", r"no action (?:needed|required)"),
    ),
    # 3. high
    Rule(H, "a customer issue", words(r"customers?", r"clients?")),
    Rule(H, "an escalation", words(r"escalat\w*")),
    Rule(H, "a blocked colleague", words(r"blocked", r"blocking", r"blocker")),
    Rule(
        H,
        "a deadline within 48 hours",
        words(r"tomorrow", r"by (?:monday|tuesday|wednesday|thursday|friday)", r"within 48 hours"),
    ),
    Rule(H, "an urgent request", words(r"urgent(?:ly)?", r"asap", r"as soon as possible")),
]

# 4. automated senders: checked on the address, after all text rules
AUTOMATED_SENDER = re.compile(
    r"^(?:no-?reply|notifications?|alerts?|bot|automated|ci|builds?|updates)@", re.IGNORECASE
)


def _result(priority: Priority, reason: str) -> Classification:
    return Classification(
        priority=priority,
        reason=reason,
        suggested_response_minutes=default_minutes(priority),
        source=ClassificationSource.FALLBACK,
    )


def classify_fallback(email: Email) -> Classification:
    """Classify one email with the rules above. Never fails."""
    text = f"{email.subject}\n{email.body}"
    for rule in RULES:
        match = rule.pattern.search(text)
        if match and (rule.also is None or rule.also.search(text)):
            found = match.group(0)[:40]
            return _result(rule.priority, f'Mentions "{found}", which signals {rule.signal}.')

    if AUTOMATED_SENDER.match(email.sender_email):
        sender = email.sender_email.split("@")[0]
        return _result(L, f'Sent by an automated address ("{sender}@"), so likely a notification.')

    return _result(
        Priority.MODERATE,
        "No urgent or low-priority signals found, so treated as a normal work request.",
    )

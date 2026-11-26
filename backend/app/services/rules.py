"""Keyword-rules priority classifier: the inbox's only classifier (no AI since #92).

Deterministic and explainable: the same text always gets the same priority, and
the reason names the keywords that decided it. No AI, no network, always available.
The rules are an ORDERED table: the first rule that matches decides the priority,
so more urgent rules come first. Order (see RULES below):

  1. critical words  (outage, breach, legal, deadline today, exec escalation, ...)
  2. clear low markers (newsletter, digest, FYI, ...) - before "high", so a
     newsletter that mentions customers stays low
  3. high words      (customer, blocked, tomorrow, ASAP, escalation, ...)
  4. automated sender (noreply@, alerts@, ...) -> low
  5. nothing matched -> moderate (a normal work request)

The reason then lists every keyword of the DECIDING priority (all its rules, in
the order found, without duplicates, at most MAX_KEYWORDS), e.g.
'Critical: matched "outage", "database is down" (an outage, a service that is down).'
"""

import re
from dataclasses import dataclass

from app.models import ClassificationSource, Email, Priority
from app.priorities import PRIORITIES, default_minutes
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


MAX_KEYWORDS = 4  # keywords named in a reason
MAX_KEYWORD_CHARS = 40  # a match like "website is unreachable" stays readable
MAX_REASON_CHARS = 200  # Classification.reason limit


def _result(priority: Priority, reason: str) -> Classification:
    return Classification(
        priority=priority,
        reason=reason,
        suggested_response_minutes=default_minutes(priority),
        source=ClassificationSource.RULES,
    )


def _matches(rule: Rule, text: str) -> list[str]:
    """Every keyword this rule finds in the text (empty if its condition fails)."""
    if rule.also is not None and not rule.also.search(text):
        return []
    return [m.group(0).strip()[:MAX_KEYWORD_CHARS] for m in rule.pattern.finditer(text)]


def _keyword_reason(priority: Priority, text: str) -> str:
    """'<Priority>: matched "a", "b" (signal, signal).' with every keyword of that priority."""
    keywords: list[str] = []
    signals: list[str] = []
    for rule in RULES:
        if rule.priority != priority:
            continue
        found = _matches(rule, text)
        if not found:
            continue
        if rule.signal not in signals:
            signals.append(rule.signal)
        for keyword in found:
            # One mention per keyword, ignoring case ("Customer" and "customer")
            if keyword.lower() not in (k.lower() for k in keywords):
                keywords.append(keyword)

    label = PRIORITIES[priority].label
    for count in range(min(len(keywords), MAX_KEYWORDS), 0, -1):
        quoted = ", ".join(f'"{k}"' for k in keywords[:count])
        # Name the signals if they fit, else just the keywords; fewer keywords as a last resort
        for reason in (
            f"{label}: matched {quoted} ({', '.join(signals)}).",
            f"{label}: matched {quoted}.",
        ):
            if len(reason) <= MAX_REASON_CHARS:
                return reason
    raise AssertionError("unreachable: one keyword always fits")  # pragma: no cover


def classify_by_rules(email: Email) -> Classification:
    """Classify one email with the rules above. Never fails."""
    text = f"{email.subject}\n{email.body}"
    for rule in RULES:
        if _matches(rule, text):
            # The first matching rule decides the priority; the reason names
            # every keyword of that priority
            return _result(rule.priority, _keyword_reason(rule.priority, text))

    if AUTOMATED_SENDER.match(email.sender_email):
        sender = email.sender_email.split("@")[0]
        return _result(L, f'Low: sent by an automated address ("{sender}@").')

    return _result(Priority.MODERATE, "Moderate: no urgent or low-priority keywords found.")

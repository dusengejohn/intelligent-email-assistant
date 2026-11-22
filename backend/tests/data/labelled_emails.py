"""Hand-labelled sample emails: each one has the priority a person would expect.

Labels follow ONLY the brief §7 meanings (written before any classifier rule, to
avoid fitting the labels to the rules). Used by the fallback tests (story 2.1) and
the accuracy eval (story 2.6). All people and companies are fictional.

Brief §7:
- critical: outage, security incident, legal/compliance, exec escalation, deadline today
- high: customer issue, manager request, deadline <= 48 h, blocked colleague
- moderate: normal work requests, meeting coordination, reviews
- low: FYI, newsletters, automated notifications, social
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from app.models import Email, Priority


@dataclass(frozen=True)
class LabelledEmail:
    sender_name: str
    sender_email: str
    subject: str
    body: str
    expected: Priority
    why: str  # why a person would choose this label

    def to_email(self) -> Email:
        """An in-memory Email row (not saved) for the classifiers."""
        return Email(
            sender_name=self.sender_name,
            sender_email=self.sender_email,
            subject=self.subject,
            body=self.body,
            received_at=datetime(2026, 11, 22, 9, 0, tzinfo=UTC),
        )


C, H, M, L = Priority.CRITICAL, Priority.HIGH, Priority.MODERATE, Priority.LOW

LABELLED: list[LabelledEmail] = [
    # --- critical ---------------------------------------------------------------
    LabelledEmail(
        "Site Monitoring",
        "alerts@monitoring.example.com",
        "Production database DOWN - checkout failing",
        "Health checks for orders-db have failed for 6 minutes. Checkout returns errors "
        "for all users. Incident channel: #inc-orders.",
        C,
        "outage, from an automated sender",
    ),
    LabelledEmail(
        "Priya Raman",
        "priya.raman@example.com",
        "Website outage affecting all customers",
        "The public website has been returning 503 for everyone since 08:40. I'm on the "
        "bridge now, please join if you can.",
        C,
        "outage (fixed example)",
    ),
    LabelledEmail(
        "Security Team",
        "security@example.org",
        "Possible breach: suspicious admin logins",
        "We saw admin logins from an unknown IP range overnight. Treat this as a security "
        "incident until we confirm otherwise. Rotate your credentials now.",
        C,
        "security incident",
    ),
    LabelledEmail(
        "Hannah Ortiz",
        "hannah.ortiz@legal.example.com",
        "Contract termination notice - legal response required",
        "We received a termination notice from a supplier. Legal needs your written "
        "summary of the delivery history before we reply.",
        C,
        "legal",
    ),
    LabelledEmail(
        "Grace Mensah",
        "grace.mensah@example.net",
        "Escalation from the CEO: Northwind account at risk",
        "The CEO just called. Northwind's director escalated the failed rollout directly "
        "to him and wants a recovery plan on his desk.",
        C,
        "exec escalation",
    ),
    LabelledEmail(
        "Victor Almeida",
        "victor.almeida@example.org",
        "Regulator filing due today at 5 PM",
        "The quarterly compliance filing is due today at 5 PM. I still need your sign-off "
        "on section 3 before I can submit it.",
        C,
        "compliance + deadline today",
    ),
    # --- high ---------------------------------------------------------------------
    LabelledEmail(
        "Dana Whitfield",
        "dana.whitfield@example.net",
        "Customer escalation: Acme order stuck for 3 days",
        "Acme's order has been stuck in fulfilment for three days and their buyer is "
        "escalating. Can you check the warehouse integration logs?",
        H,
        "customer issue (fixed example)",
    ),
    LabelledEmail(
        "Tomasz Wrona",
        "tomasz.wrona@example.com",
        "Blocked on API credentials for the release",
        "I can't finish the release pipeline until I get the payment API credentials. "
        "Could you share them in the vault?",
        H,
        "blocked colleague",
    ),
    LabelledEmail(
        "Marcus Lindqvist",
        "marcus.lindqvist@example.org",
        "Budget numbers needed by tomorrow noon",
        "Finance needs the infrastructure budget numbers by tomorrow noon for the planning "
        "deck. A rough estimate is fine.",
        H,
        "deadline within 48 h",
    ),
    LabelledEmail(
        "Elena Brandt",
        "elena.brandt@example.com",
        "Can you send me the Q3 slides ASAP?",
        "I'm presenting to the leadership team after lunch and need your Q3 capacity "
        "slides ASAP. Thanks!",
        H,
        "manager request, urgent",
    ),
    LabelledEmail(
        "Owen Calder",
        "owen.calder@example.net",
        "Client reports wrong amounts on invoice",
        "Fairview's finance team says last month's invoice double-charged two line items. "
        "They'd like a corrected invoice.",
        H,
        "customer issue",
    ),
    LabelledEmail(
        "Sana Okafor",
        "sana.okafor@example.org",
        "Vendor contract review by Friday",
        "Please review the renewal terms for the monitoring vendor by Friday so procurement "
        "can sign next week.",
        H,
        "deadline within 48 h",
    ),
    # --- moderate -------------------------------------------------------------------
    LabelledEmail(
        "Hiroshi Tanaka",
        "hiroshi.tanaka@example.org",
        "Can we meet Thursday to plan the migration?",
        "I'd like 30 minutes on Thursday afternoon to walk through the storage migration "
        "plan. Does 2 PM work for you?",
        M,
        "meeting coordination (fixed example)",
    ),
    LabelledEmail(
        "Lena Fischer",
        "lena.fischer@example.com",
        "Review request: logging refactor PR #212",
        "When you have time, could you review my logging refactor? It touches the request "
        "middleware and the log format.",
        M,
        "review",
    ),
    LabelledEmail(
        "Ravi Patel",
        "ravi.patel@example.net",
        "Draft onboarding guide for your feedback",
        "Attached is the first draft of the onboarding guide for new engineers. Comments "
        "welcome in the doc.",
        M,
        "normal work request",
    ),
    LabelledEmail(
        "Chloe Martin",
        "chloe.martin@example.org",
        "Room change for the sprint retro",
        "The retro moves from room 4B to 2A because of the projector. Same time as usual.",
        M,
        "meeting coordination",
    ),
    LabelledEmail(
        "Ben Adeyemi",
        "ben.adeyemi@example.com",
        "Should we slow down the release train?",
        "Several teams asked for more time to test. Should we slow down to one release "
        "every two weeks? Happy to discuss at the next sync.",
        M,
        "tricky: 'slow down' is not an outage",
    ),
    LabelledEmail(
        "Mei Lin",
        "mei.lin@example.net",
        "Downloaded the logs you asked for",
        "I downloaded last week's access logs and put the breakdown by endpoint in the "
        "shared folder.",
        M,
        "tricky: 'download' and 'breakdown' contain 'down'",
    ),
    # --- low --------------------------------------------------------------------------
    LabelledEmail(
        "Engineering Newsletter",
        "newsletter@example.com",
        "Weekly engineering newsletter",
        "This week: new on-call handbook, a talk on observability, and three open roles. "
        "Unsubscribe at any time.",
        L,
        "newsletter (fixed example)",
    ),
    LabelledEmail(
        "CI",
        "noreply@ci.example.com",
        "Build #4512 succeeded",
        "Pipeline main #4512 finished successfully in 7m 12s. All 312 tests passed.",
        L,
        "automated notification (fixed example)",
    ),
    LabelledEmail(
        "Customer Success",
        "updates@example.org",
        "Monthly digest: customer success stories",
        "This month's digest features three customers who cut their costs with the new "
        "plan. Read the full stories on the intranet.",
        L,
        "tricky: newsletter that mentions customers",
    ),
    LabelledEmail(
        "Facilities",
        "facilities@example.net",
        "FYI: office closed Monday for maintenance",
        "FYI, the office is closed on Monday for electrical maintenance. Remote work as usual.",
        L,
        "FYI",
    ),
    LabelledEmail(
        "Social Committee",
        "social@example.com",
        "Pizza Friday in the kitchen",
        "Join us for pizza in the kitchen at noon on Friday. Vegetarian options included!",
        L,
        "social (hard for keyword rules)",
    ),
]

# The five fixed examples from the Epic 2 issue (#3)
FIXED_EXAMPLES = [e for e in LABELLED if "(fixed example)" in e.why]

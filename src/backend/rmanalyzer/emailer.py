"""
SummaryEmail class for RMAnalyzer.
"""
import os
import yattag
from .models import Group, Category
from .transactions import to_currency
from .azure_utils import send_email

__all__ = ["SummaryEmail"]

class SummaryEmail:
    """Formats and sends a summary email for a group of people."""
    def __init__(self, sender: str, to: list[str]) -> None:
        self.sender = sender
        self.to = to
        self.subject = str()
        self.body = str()

    def add_body(self, group: Group) -> None:
        doc, tag, text = yattag.Doc().tagtext()
        doc.asis("<!DOCTYPE html>")
        with tag("html"):
            with tag("head"):
                doc.asis(
                    "<style>table {border-collapse: collapse; width: 100%} "
                    "th, td {border: 1px solid black; padding: 8px 12px; text-align: left;} "
                    "th {background-color: #f2f2f2;}</style>"
                )
            with tag("body"):
                with tag("table", border="1"):
                    with tag("thead"):
                        with tag("tr"):
                            with tag("th"):
                                text("")
                            for c in Category:
                                with tag("th"):
                                    text(c.value)
                            with tag("th"):
                                text("Total")
                    with tag("tbody"):
                        for p in group.members:
                            with tag("tr"):
                                with tag("td"):
                                    text(p.name)
                                for c in Category:
                                    with tag("td"):
                                        text(to_currency(p.get_expenses(c)))
                                with tag("td"):
                                    text(to_currency(p.get_expenses()))
                        if len(group.members) == 2:
                            p1, p2 = group.members
                            with tag("tr"):
                                with tag("td"):
                                    text("Difference")
                                for c in Category:
                                    with tag("td"):
                                        text(to_currency(group.get_expenses_difference(p1, p2, c)))
                                with tag("td"):
                                    text(to_currency(group.get_expenses_difference(p1, p2)))
                if len(group.members) == 2:
                    p1, p2 = group.members
                    scale = 0.445
                    msg = (
                        f"Using a scale factor of {scale} for {p1.name}, "
                        f"{p1.name} owes {p2.name}: {to_currency(group.get_debt(p1, p2, scale))}"
                    )
                    with tag("p"):
                        text(msg)
        self.body = doc.getvalue()

    def add_subject(self, group: Group) -> None:
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        self.subject = f"Transactions Summary: {min_date.strftime('%m/%d/%y')} - {max_date.strftime('%m/%d/%y')}"

    def send(self) -> None:
        # Fetch Endpoint from environment variable (Managed Identity used implicitly)
        endpoint = os.environ.get("COMMUNICATION_SERVICES_ENDPOINT")
        if not endpoint:
            raise ValueError("COMMUNICATION_SERVICES_ENDPOINT not set")

        send_email(endpoint, self.sender, self.to, self.subject, self.body)

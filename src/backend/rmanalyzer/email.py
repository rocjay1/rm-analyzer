"""
SummaryEmail class for RMAnalyzer.
"""

import logging
import os

import yattag
from azure.communication.email import EmailClient
from azure.identity import DefaultAzureCredential

from .models import Category, Group, to_currency

__all__ = ["SummaryEmail", "send_email", "send_error_email"]

logger = logging.getLogger(__name__)


def send_error_email(sender: str, recipients: list[str], errors: list[str]) -> None:
    """Helper to send an email with validation errors."""
    if not sender or not recipients:
        return

    subject = "RMAnalyzer - Upload Failed"
    error_list = "".join([f"<li>{e}</li>" for e in errors])
    body = f"""
    <h3>Upload Failed</h3>
    <p>The uploaded CSV could not be processed due to the following errors:</p>
    <ul>{error_list}</ul>
    """
    try:
        # Get Endpoint
        endpoint = os.environ.get("COMMUNICATION_SERVICES_ENDPOINT")
        if endpoint:
            send_email(endpoint, sender, recipients, subject, body)
        else:
            logger.error(
                "COMMUNICATION_SERVICES_ENDPOINT not set, cannot send error email."
            )
    except Exception as email_ex:  # pylint: disable=broad-exception-caught
        logger.error("Failed to send error email: %s", email_ex)


def send_email(
    endpoint: str, sender: str, to: list[str], subject: str, body: str
) -> None:
    """Send an email using Azure Communication Services and Managed Identity."""
    try:
        credential = DefaultAzureCredential()
        email_client = EmailClient(endpoint=endpoint, credential=credential)

        message = {
            "senderAddress": sender,
            "recipients": {
                "to": [{"address": email} for email in to],
            },
            "content": {
                "subject": subject,
                "plainText": "Please view this email in a client that supports HTML.",
                "html": body,
            },
        }

        poller = email_client.begin_send(message)
        result = poller.result()

        # Extract message ID (result might be dict or object)
        message_id = None
        if isinstance(result, dict):
            message_id = (
                result.get("messageId") or result.get("message_id") or result.get("id")
            )
        else:
            message_id = getattr(result, "message_id", None) or getattr(
                result, "id", None
            )

        if message_id:
            logger.info("Email sent with message ID: %s", message_id)
        else:
            logger.info("Email sent successfully")

    except Exception as ex:
        logger.error("Error sending email: %s", ex)
        raise


class SummaryEmail:
    """Formats and sends a summary email for a group of people."""

    def __init__(self, sender: str, to: list[str], errors: list[str] = None) -> None:
        self.sender = sender
        self.to = to
        self.errors = errors or []
        self.subject = str()
        self.body = str()

    def add_body(self, group: Group) -> None:
        """Generate the HTML body of the email based on the group's expenses."""
        tracked_categories = [c for c in Category if c != Category.OTHER]
        doc, tag, text = yattag.Doc().tagtext()
        doc.asis("<!DOCTYPE html>")
        with tag("html"):
            with tag("head"):
                doc.asis(
                    "<style>table {border-collapse: collapse; width: 100%} "
                    "th, td {border: 1px solid black; padding: 8px 12px; text-align: left;} "
                    "th {background-color: #f2f2f2;} "
                    ".error {color: red;}</style>"
                )
            with tag("body"):
                if self.errors:
                    with tag("div", klass="error"):
                        with tag("h3"):
                            text("⚠️ Warning: Some transactions were skipped")
                        with tag("ul"):
                            for error in self.errors:
                                with tag("li"):
                                    text(error)
                        with tag("hr"):
                            pass

                with tag("table", border="1"):
                    with tag("thead"):
                        with tag("tr"):
                            with tag("th"):
                                text("")
                            for c in tracked_categories:
                                with tag("th"):
                                    text(c.value)
                            with tag("th"):
                                text("Total")
                    with tag("tbody"):
                        for p in group.members:
                            with tag("tr"):
                                with tag("td"):
                                    text(p.name)
                                for c in tracked_categories:
                                    with tag("td"):
                                        text(to_currency(p.get_expenses(c)))
                                with tag("td"):
                                    text(to_currency(p.get_expenses()))
                        if len(group.members) == 2:
                            p1, p2 = group.members
                            with tag("tr"):
                                with tag("td"):
                                    text("Difference")
                                for c in tracked_categories:
                                    with tag("td"):
                                        text(
                                            to_currency(
                                                group.get_expenses_difference(p1, p2, c)
                                            )
                                        )
                                with tag("td"):
                                    text(
                                        to_currency(
                                            group.get_expenses_difference(p1, p2)
                                        )
                                    )
                if len(group.members) == 2:
                    p1, p2 = group.members
                    msg = f"{p1.name} owes {p2.name}: {to_currency(group.get_debt(p1, p2))}"
                    with tag("p"):
                        text(msg)
        self.body = doc.getvalue()

    def add_subject(self, group: Group) -> None:
        """Set the email subject based on the transaction date range."""
        min_date = group.get_oldest_transaction()
        max_date = group.get_newest_transaction()
        self.subject = f"Transactions Summary: {min_date.strftime('%m/%d/%y')} - {max_date.strftime('%m/%d/%y')}"

    def send(self) -> None:
        """Send the email using Azure Communication Services."""
        # Fetch Endpoint from environment variable (Managed Identity used implicitly)
        endpoint = os.environ.get("COMMUNICATION_SERVICES_ENDPOINT")
        if not endpoint:
            raise ValueError("COMMUNICATION_SERVICES_ENDPOINT not set")

        send_email(endpoint, self.sender, self.to, self.subject, self.body)

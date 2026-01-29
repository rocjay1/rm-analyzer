"""Service for sending emails via Azure Communication Services."""

import logging
import os
from azure.communication.email import EmailClient
from azure.identity import DefaultAzureCredential
from .email_renderer import EmailRenderer

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via Azure Communication Services."""

    def __init__(self) -> None:
        self._endpoint = os.environ.get("COMMUNICATION_SERVICES_ENDPOINT")
        self._sender = os.environ.get("SENDER_EMAIL")

        if not self._endpoint:
            raise ValueError(
                "COMMUNICATION_SERVICES_ENDPOINT environment variable is not set."
            )
        if not self._sender:
            raise ValueError("SENDER_EMAIL environment variable is not set.")

        self._email_client: EmailClient | None = None

    def _get_email_client(self) -> EmailClient:
        """Returns an EmailClient, creating it if necessary."""
        if self._email_client:
            return self._email_client

        # Ensure endpoint is present (already validated in __init__)
        assert self._endpoint is not None

        credential = DefaultAzureCredential()
        self._email_client = EmailClient(endpoint=self._endpoint, credential=credential)
        return self._email_client

    def send_email(self, to: list[str], subject: str, body: str) -> None:
        """Send an email using Azure Communication Services and Managed Identity."""
        try:
            email_client = self._get_email_client()

            message = {
                "senderAddress": self._sender,
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
                    result.get("messageId")
                    or result.get("message_id")
                    or result.get("id")
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

    def send_error_email(self, recipients: list[str], errors: list[str]) -> None:
        """Helper to send an email with validation errors."""
        subject = "RMAnalyzer - Upload Failed"
        body = EmailRenderer.render_error_body(errors)
        self.send_email(recipients, subject, body)

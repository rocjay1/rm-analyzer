"""
Azure Communication Services utility functions for RMAnalyzer.
"""
import logging
from azure.identity import DefaultAzureCredential
from azure.communication.email import EmailClient

__all__ = ["send_email"]

logger = logging.getLogger(__name__)

def send_email(endpoint: str, sender: str, to: list[str], subject: str, body: str) -> None:
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
        logger.info("Email sent with message ID: %s", result["messageId"])
        
    except Exception as ex:
        logger.error("Error sending email: %s", ex)
        raise

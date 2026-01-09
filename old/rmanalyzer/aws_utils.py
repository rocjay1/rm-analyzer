"""
AWS S3 and SES utility functions for RMAnalyzer.

This module provides helpers for S3 file access and SES email sending.
"""
import logging
import boto3
from botocore import exceptions
from mypy_boto3_s3.client import S3Client
from mypy_boto3_s3.type_defs import GetObjectOutputTypeDef
from mypy_boto3_ses.client import SESClient

__all__ = ["get_s3_content", "send_email"]

logger = logging.getLogger(__name__)


def get_s3_content(bucket: str, key: str) -> str:
    """Read the contents of an S3 object as a UTF-8 string."""
    s3: S3Client = boto3.client("s3")
    try:
        response: GetObjectOutputTypeDef = s3.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")
    except exceptions.ClientError as ex:
        logger.error("Error reading S3 file: %s", ex)
        raise

def send_email(sender: str, to: list[str], subject: str, body: str) -> None:
    """Send an email using AWS SES."""
    ses: SESClient = boto3.client("ses", region_name="us-east-1")
    try:
        ses.send_email(
            Source=sender,
            Destination={"ToAddresses": to},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": body}, "Text": {"Data": body}},
            },
        )
    except exceptions.ClientError as ex:
        logger.error("Error sending email: %s", ex)
        raise

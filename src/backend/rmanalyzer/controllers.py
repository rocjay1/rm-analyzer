"""
Controllers for handling application logic.
"""

import base64
import json
import logging
import os
from datetime import datetime
from http import HTTPStatus

import azure.functions as func
from rmanalyzer import db, storage
from rmanalyzer.email import SummaryEmail, send_error_email
from rmanalyzer.models import Group, Person, get_transactions

__all__ = [
    "handle_upload_async",
    "handle_savings_dbrequest",
    "process_queue_item",
]

logger = logging.getLogger(__name__)


# Limit file size to 10MB to prevent DoS
MAX_FILE_SIZE = 10 * 1024 * 1024


def _get_user_email(req: func.HttpRequest) -> str | None:
    """
    Parses the 'x-ms-client-principal' header to get the user's email (userDetails).
    Returns None if header is missing or invalid.
    """
    header = req.headers.get("x-ms-client-principal")
    if not header:
        return None

    try:
        decoded = base64.b64decode(header).decode("utf-8")
        principal = json.loads(decoded)
        return principal.get("userDetails")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Failed to parse x-ms-client-principal: %s", e)
        return None


def _get_uploaded_file_content(
    req: func.HttpRequest,
) -> tuple[str, bytes, func.HttpResponse | None]:
    """
    Helper to extract and validate uploaded file content.
    Returns (filename, content_bytes, error_response).
    """
    if not req.files:
        return (
            "",
            b"",
            func.HttpResponse(
                "No file found in request.", status_code=HTTPStatus.BAD_REQUEST
            ),
        )

    file_key = list(req.files.keys())[0]
    uploaded_file = req.files[file_key]
    filename = uploaded_file.filename or "upload.csv"

    file_content = uploaded_file.stream.read(MAX_FILE_SIZE + 1)
    if len(file_content) > MAX_FILE_SIZE:
        return (
            "",
            b"",
            func.HttpResponse(
                f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB.",
                status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            ),
        )

    return filename, file_content, None


def handle_upload_async(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receives a CSV, uploads it to Blob Storage, and queues a processing message.
    Returns 202 Accepted.
    """
    logging.info("Processing async upload request.")

    if "x-ms-client-principal" not in req.headers:
        return func.HttpResponse("Unauthorized", status_code=HTTPStatus.UNAUTHORIZED)

    try:
        # 1. Extract File
        filename, content, error_resp = _get_uploaded_file_content(req)
        if error_resp:
            return error_resp

        # 2. Upload to Blob Storage
        # Generate a unique name to avoid overwrites (though blob_utils handles it, good practice)
        base_name = os.path.basename(filename)
        blob_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{base_name}"

        blob_url = storage.upload_csv(blob_name, content)
        logging.info("Uploaded blob: %s", blob_url)

        # 3. Enqueue Message
        storage.enqueue_message({"blob_name": blob_name})
        logging.info("Enqueued processing message for: %s", blob_name)

        return func.HttpResponse(
            "Upload accepted for processing.",
            status_code=HTTPStatus.ACCEPTED,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error during async upload: %s", e)
        return func.HttpResponse(
            f"Upload Error: {str(e)}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )


def process_queue_item(msg: func.QueueMessage) -> None:
    """
    Queue Trigger handler. Downloads CSV, analyzes it, saves to DB, and emails summary.
    """
    try:
        message_body = msg.get_body().decode("utf-8")
        logging.info("Processing queue item: %s", message_body)

        data = json.loads(message_body)
        blob_name = data.get("blob_name")

        if not blob_name:
            logging.error("Invalid message: missing blob_name")
            return

        # 1. Download CSV
        csv_content = storage.download_csv(blob_name)

        # 3. Analysis
        transactions, errors = get_transactions(csv_content)

        # Retrieve People from DB
        people_data = db.get_all_people()
        members = [Person.from_config(p) for p in people_data]

        if errors and len(transactions) == 0:
            logging.error("CSV Validation Errors: %s", errors)

            # Send Error Email
            sender = os.environ.get("SENDER_EMAIL")

            # Send to all members logic, mirroring summary email logic.
            recipients = [p.email for p in members]

            if sender:
                send_error_email(sender, recipients, errors)
            else:
                logging.error("Sender email not configured, cannot send error email.")

            return

        # 4. Save to DB
        try:
            db.save_transactions(transactions)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Failed to save transactions to DB: %s", e)

        # 5. Email
        # Re-using members fetched above
        group = Group(members)
        group.add_transactions(transactions)

        if not any(p.transactions for p in group.members):
            logging.warning("No valid transactions found for configured accounts.")
            return

        sender = os.environ.get("SENDER_EMAIL")

        if not sender:
            logging.error("Sender email not configured.")
            return

        email = SummaryEmail(sender, [p.email for p in group.members], errors=errors)
        email.add_body(group)
        email.add_subject(group)
        email.send()

        logging.info("Processing complete for %s", blob_name)

    except Exception as e:
        logging.error("Error processing queue item: %s", e)
        # Raising exception ensures the message goes to poison queue after retries
        raise


def handle_savings_dbrequest(req: func.HttpRequest) -> func.HttpResponse:
    """Handles getting and updating savings calculation data."""
    logging.info("Processing savings request.")

    user_email = _get_user_email(req)
    if not user_email:
        return func.HttpResponse("Unauthorized", status_code=HTTPStatus.UNAUTHORIZED)

    try:
        # Default month to current month if not provided
        current_month = datetime.now().strftime("%Y-%m")

        if req.method == "GET":
            month = req.params.get("month", current_month)
            data = db.get_savings(month, user_email)
            if data is None:
                return func.HttpResponse("Not Found", status_code=HTTPStatus.NOT_FOUND)

            return func.HttpResponse(
                json.dumps(data),
                mimetype="application/json",
                status_code=HTTPStatus.OK,
            )

        if req.method == "POST":
            try:
                req_body = req.get_json()
            except ValueError:
                return func.HttpResponse(
                    "Invalid JSON", status_code=HTTPStatus.BAD_REQUEST
                )

            month = req_body.get("month", current_month)

            # Basic validation (allow empty items, but check structure)
            if "startingBalance" not in req_body:
                return func.HttpResponse(
                    "Missing required fields", status_code=HTTPStatus.BAD_REQUEST
                )

            db.save_savings(month, req_body, user_email)
            return func.HttpResponse("Saved successfully", status_code=HTTPStatus.OK)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error in savings handler: %s", e)
        return func.HttpResponse(
            f"Internal Error: {str(e)}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR
        )

    return func.HttpResponse(
        "Method not supported", status_code=HTTPStatus.METHOD_NOT_ALLOWED
    )

"""
Controllers for handling application logic.
"""

import functools
import json
import logging
import os
from datetime import datetime

import azure.functions as func
from rmanalyzer import blob_utils, db, queue_utils
from rmanalyzer.config import get_config_from_str, validate_config
from rmanalyzer.emailer import SummaryEmail
from rmanalyzer.mail_utils import send_email
from rmanalyzer.models import Group, Person
from rmanalyzer.transactions import get_transactions

__all__ = [
    "handle_upload_async",
    "handle_savings_dbrequest",
    "process_queue_item",
    "get_config",
    "get_members",
]

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

# Limit file size to 10MB to prevent DoS
MAX_FILE_SIZE = 10 * 1024 * 1024


@functools.lru_cache(maxsize=1)
def get_config() -> dict:
    """Load and validate configuration, using cache if available."""
    config = None
    # Try Environment Variable (Production)
    env_config = os.environ.get("APP_CONFIG_JSON")
    if env_config:
        try:
            config = get_config_from_str(env_config)
        except json.JSONDecodeError as e:
            logging.error("Failed to parse APP_CONFIG_JSON: %s", e)

    # Try File (Local Dev) if env var failed or not set
    if config is None and os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Failed to load local config file: %s", e)

    if config is None:
        raise FileNotFoundError(
            "Configuration file not found on server (and APP_CONFIG_JSON not set)."
        )

    validate_config(config)
    return config


def get_members(people_config: list[dict]) -> list[Person]:
    """Convert config dicts to Person objects."""
    return [Person(p["Name"], p["Email"], p["Accounts"], []) for p in people_config]


def _get_uploaded_file_content(
    req: func.HttpRequest,
) -> tuple[str, bytes, func.HttpResponse | None]:
    """
    Helper to extract and validate uploaded file content.
    Returns (filename, content_bytes, error_response).
    """
    if not req.files:
        return "", b"", func.HttpResponse("No file found in request.", status_code=400)

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
                status_code=413,
            ),
        )

    return filename, file_content, None


def _send_error_email(sender: str, recipients: list[str], errors: list[str]) -> None:
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
            logging.error(
                "COMMUNICATION_SERVICES_ENDPOINT not set, cannot send error email."
            )
    except Exception as email_ex:  # pylint: disable=broad-exception-caught
        logging.error("Failed to send error email: %s", email_ex)


def handle_upload_async(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receives a CSV, uploads it to Blob Storage, and queues a processing message.
    Returns 202 Accepted.
    """
    logging.info("Processing async upload request.")

    if "x-ms-client-principal" not in req.headers:
        return func.HttpResponse("Unauthorized", status_code=401)

    try:
        # 1. Extract File
        filename, content, error_resp = _get_uploaded_file_content(req)
        if error_resp:
            return error_resp

        # 2. Upload to Blob Storage
        # Generate a unique name to avoid overwrites (though blob_utils handles it, good practice)
        base_name = os.path.basename(filename)
        blob_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{base_name}"

        blob_url = blob_utils.upload_csv(blob_name, content)
        logging.info("Uploaded blob: %s", blob_url)

        # 3. Enqueue Message
        queue_utils.enqueue_message({"blob_name": blob_name})
        logging.info("Enqueued processing message for: %s", blob_name)

        return func.HttpResponse(
            "Upload accepted for processing.",
            status_code=202,
        )

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error during async upload: %s", e)
        return func.HttpResponse(f"Upload Error: {str(e)}", status_code=500)


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
        csv_content = blob_utils.download_csv(blob_name)

        # 2. Load Config
        try:
            config = get_config()
        except FileNotFoundError:
            logging.error("Configuration file not found.")
            return

        # 3. Analysis
        transactions, errors = get_transactions(csv_content)

        # Retrieve People from DB
        people_data = db.get_all_people()
        members = get_members(people_data)

        # If critical errors (e.g. empty file), we might stop.
        # But for row errors, we might still proceed with valid ones?
        # Current logic: if ANY errors, we abort email?
        # Original logic returned 400. Here we can't return 400.
        # We should probably log errors or email them.
        if errors and len(transactions) == 0:
            logging.error("CSV Validation Errors: %s", errors)

            # Send Error Email
            sender = os.environ.get("SENDER_EMAIL")
            if not sender and config:
                sender = config.get("SenderEmail")

            # Send to all members logic, mirroring summary email logic.
            recipients = [p.email for p in members]

            if sender:
                _send_error_email(sender, recipients, errors)
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
        if not sender and config:
            sender = config.get("SenderEmail")

        if not sender:
            logging.error("Sender email not configured.")
            return

        email = SummaryEmail(sender, [p.email for p in group.members])
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

    try:
        # Default month to current month if not provided
        current_month = datetime.now().strftime("%Y-%m")

        if req.method == "GET":
            month = req.params.get("month", current_month)
            data = db.get_savings(month)
            return func.HttpResponse(
                json.dumps(data), mimetype="application/json", status_code=200
            )

        if req.method == "POST":
            try:
                req_body = req.get_json()
            except ValueError:
                return func.HttpResponse("Invalid JSON", status_code=400)

            month = req_body.get("month", current_month)

            # Basic validation (allow empty items, but check structure)
            if "startingBalance" not in req_body:
                return func.HttpResponse("Missing required fields", status_code=400)

            db.save_savings(month, req_body)
            return func.HttpResponse("Saved successfully", status_code=200)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.error("Error in savings handler: %s", e)
        return func.HttpResponse(f"Internal Error: {str(e)}", status_code=500)

    return func.HttpResponse("Method not supported", status_code=405)

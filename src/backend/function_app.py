"""
Azure Function App entry point for RMAnalyzer.
"""

import json
import logging
import os
from typing import Optional, Tuple

import azure.functions as func
from rmanalyzer.config import get_config_from_str, validate_config
from rmanalyzer.emailer import SummaryEmail
from rmanalyzer.models import Group, Person
from rmanalyzer.transactions import get_transactions
from rmanalyzer.storage import load_savings_data, save_savings_data

app = func.FunctionApp()

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_CONFIG_CACHE = None

# Limit file size to 10MB to prevent DoS
MAX_FILE_SIZE = 10 * 1024 * 1024


def get_config() -> dict:
    """Load and validate configuration, using cache if available."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE:
        return _CONFIG_CACHE

    config = None
    # 1. Try Environment Variable (Production)
    env_config = os.environ.get("APP_CONFIG_JSON")
    if env_config:
        config = get_config_from_str(env_config)
    elif os.path.exists(CONFIG_PATH):
        # 2. Try File (Local Dev)
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    if config is None:
        raise FileNotFoundError(
            "Configuration file not found on server (and APP_CONFIG_JSON not set)."
        )

    validate_config(config)
    _CONFIG_CACHE = config
    return config


def get_members(people_config: list[dict]) -> list[Person]:
    """Convert config dicts to Person objects."""
    return [Person(p["Name"], p["Email"], p["Accounts"], []) for p in people_config]


def _get_uploaded_file_content(
    req: func.HttpRequest,
) -> Tuple[str, Optional[func.HttpResponse]]:
    """Helper to extract and validate uploaded file content."""
    if not req.files:
        return "", func.HttpResponse("No file found in request.", status_code=400)

    file_key = list(req.files.keys())[0]
    uploaded_file = req.files[file_key]

    file_content = uploaded_file.stream.read(MAX_FILE_SIZE + 1)
    if len(file_content) > MAX_FILE_SIZE:
        return "", func.HttpResponse(
            f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB.",
            status_code=413,
        )

    try:
        return file_content.decode("utf-8"), None
    except UnicodeDecodeError:
        return "", func.HttpResponse(
            "Invalid file encoding. Please upload a valid UTF-8 CSV.",
            status_code=400,
        )


@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload_and_analyze(req: func.HttpRequest) -> func.HttpResponse:
    """Receives a CSV, processes it immediately using local config, and sends an email."""
    logging.info("Processing upload and analysis request.")

    # Security check: Ensure the request is coming via Static Web App Authentication
    client_principal = req.headers.get("x-ms-client-principal")
    if not client_principal:
        return func.HttpResponse(
            "Unauthorized: Requests must be authenticated via Static Web App.",
            status_code=401,
        )

    try:
        csv_content, error_resp = _get_uploaded_file_content(req)
        if error_resp:
            return error_resp

        # 2. Load Local Configuration
        try:
            config = get_config()
        except FileNotFoundError:
            return func.HttpResponse(
                "Configuration file not found on server.", status_code=500
            )

        # 3. Run Analysis
        transactions, errors = get_transactions(csv_content)

        if errors:
            # If there are parsing errors, we abort and return them to the user.
            error_msg = "CSV Validation Errors:\n" + "\n".join(errors[:20])
            if len(errors) > 20:
                error_msg += f"\n... and {len(errors) - 20} more errors."
            return func.HttpResponse(error_msg, status_code=400)

        members = get_members(config["People"])
        group = Group(members)
        group.add_transactions(transactions)

        if not any(p.transactions for p in group.members):
            return func.HttpResponse(
                "No valid transactions found in the file for configured accounts.",
                status_code=400,
            )

        # 4. Send Email
        sender = os.environ.get("SENDER_EMAIL", config.get("SenderEmail"))
        if not sender:
            return func.HttpResponse("Sender email not configured.", status_code=500)

        email = SummaryEmail(sender, [p.email for p in group.members])
        email.add_body(group)
        email.add_subject(group)
        email.send()

        return func.HttpResponse(
            "Analysis complete. Summary email sent.", status_code=200
        )

    except Exception as e:
        logging.error("Error during immediate processing: %s", e)
        return func.HttpResponse(f"Processing Error: {str(e)}", status_code=500)


@app.route(
    route="savings", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS
)
def savings_handler(req: func.HttpRequest) -> func.HttpResponse:
    """Handles getting and updating savings calculation data."""
    logging.info("Processing savings request.")

    # Security check: Ensure the request is coming via Static Web App Authentication
    # (Optional: you might want to uncomment this for production security)
    # client_principal = req.headers.get("x-ms-client-principal")
    # if not client_principal:
    #     return func.HttpResponse(
    #         "Unauthorized: Requests must be authenticated via Static Web App.",
    #         status_code=401,
    #     )

    try:
        if req.method == "GET":
            data = load_savings_data()
            return func.HttpResponse(
                json.dumps(data), mimetype="application/json", status_code=200
            )

        elif req.method == "POST":
            try:
                req_body = req.get_json()
            except ValueError:
                return func.HttpResponse("Invalid JSON", status_code=400)

            # Basic validation
            if "startingBalance" not in req_body or "items" not in req_body:
                return func.HttpResponse("Missing required fields", status_code=400)

            save_savings_data(req_body)
            return func.HttpResponse("Saved successfully", status_code=200)

    except Exception as e:
        logging.error(f"Error in savings handler: {e}")
        return func.HttpResponse(f"Internal Error: {str(e)}", status_code=500)

    return func.HttpResponse("Method not supported", status_code=405)

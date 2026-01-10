import logging
import os
import json
import azure.functions as func

from rmanalyzer.config import validate_config
from rmanalyzer.transactions import get_transactions
from rmanalyzer.models import Person, Group
from rmanalyzer.emailer import SummaryEmail

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

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError("Configuration file not found on server.")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    validate_config(config)
    _CONFIG_CACHE = config
    return config

def get_members(people_config: list[dict]) -> list[Person]:
    return [
        Person(
            p["Name"],
            p["Email"],
            p["Accounts"],
            []
        )
        for p in people_config
    ]

@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload_and_analyze(req: func.HttpRequest) -> func.HttpResponse:
    """Receives a CSV, processes it immediately using local config, and sends an email."""
    logging.info('Processing upload and analysis request.')

    # Security check: Ensure the request is coming via Static Web App Authentication
    client_principal = req.headers.get("x-ms-client-principal")
    if not client_principal:
        return func.HttpResponse(
            "Unauthorized: Requests must be authenticated via Static Web App.",
            status_code=401
        )

    try:
        # 1. Get the uploaded file
        if not req.files:
            return func.HttpResponse("No file found in request.", status_code=400)

        file_key = list(req.files.keys())[0]
        uploaded_file = req.files[file_key]
        filename = uploaded_file.filename

        # Security: Check file content length if available, though stream reading is better
        # We read into memory, so strict limit is needed.
        # However, req.files wraps werkzeug/builtin storage.
        # reading stream allows checking size.

        file_content = uploaded_file.stream.read(MAX_FILE_SIZE + 1)
        if len(file_content) > MAX_FILE_SIZE:
             return func.HttpResponse(f"File too large. Maximum size is {MAX_FILE_SIZE/1024/1024}MB.", status_code=413)

        try:
            csv_content = file_content.decode("utf-8")
        except UnicodeDecodeError:
             return func.HttpResponse("Invalid file encoding. Please upload a valid UTF-8 CSV.", status_code=400)

        # 2. Load Local Configuration
        try:
            config = get_config()
        except FileNotFoundError:
            return func.HttpResponse("Configuration file not found on server.", status_code=500)

        # 3. Run Analysis
        transactions, errors = get_transactions(csv_content)

        if errors:
            # If there are parsing errors, we abort and return them to the user.
            error_msg = "CSV Validation Errors:\n" + "\n".join(errors[:20]) # Limit output
            if len(errors) > 20:
                error_msg += f"\n... and {len(errors) - 20} more errors."
            return func.HttpResponse(error_msg, status_code=400)

        members = get_members(config["People"])
        group = Group(members)
        group.add_transactions(transactions)

        if not any(p.transactions for p in group.members):
             return func.HttpResponse(
                "No valid transactions found in the file for configured accounts.",
                status_code=400
            )

        # 4. Send Email
        sender = os.environ.get("SENDER_EMAIL", config.get("SenderEmail"))
        if not sender:
            return func.HttpResponse("Sender email not configured.", status_code=500)

        email = SummaryEmail(sender, [p.email for p in group.members])
        email.add_body(group)
        email.add_subject(group)
        email.send()

        return func.HttpResponse(f"Analysis complete. Summary email sent for '{filename}'.", status_code=200)

    except Exception as e:
        logging.error("Error during immediate processing: %s", e)
        return func.HttpResponse(f"Processing Error: {str(e)}", status_code=500)

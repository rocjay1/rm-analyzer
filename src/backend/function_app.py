"""
Azure Function App entry point for RMAnalyzer.
"""

import azure.functions as func
from rmanalyzer import controller

app = func.FunctionApp()


@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receives a CSV, uploads to Blob, enqueues message, returns 202.

    Security Note:
    auth_level=ANONYMOUS is used because the function relies on Azure App Service Authentication
    (Easy Auth) which is configured at the platform level. The application logic verifies the
    'x-ms-client-principal' header to ensure requests are authenticated.
    """
    return controller.controller.handle_upload_async(req)


@app.queue_trigger(
    arg_name="msg", queue_name="%QUEUE_NAME%", connection="StorageConnection"
)
def process_upload_queue(msg: func.QueueMessage) -> None:
    """Processes a queued upload message."""
    controller.controller.process_queue_item(msg)


@app.route(
    route="savings", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS
)
def handle_savings(req: func.HttpRequest) -> func.HttpResponse:
    """Handles getting and updating savings calculation data."""
    return controller.controller.handle_savings_dbrequest(req)


@app.route(route="sync-data", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def sync_data(req: func.HttpRequest) -> func.HttpResponse:
    """Syncs data from extension."""
    return controller.controller.handle_sync_data(req)


@app.route(
    route="cards", methods=["GET", "POST", "PUT"], auth_level=func.AuthLevel.ANONYMOUS
)
def cards(req: func.HttpRequest) -> func.HttpResponse:
    """Handles credit card management."""
    return controller.controller.handle_cards(req)


@app.schedule(
    schedule="0 0 9 * * *",  # Daily at 9 AM
    arg_name="timer",
    run_on_startup=False,
    use_monitor=False,
)
def check_reminders(timer: func.TimerRequest) -> None:
    """Checks for payment due dates and sends reminders."""
    controller.controller.check_reminders()

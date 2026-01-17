"""
Azure Function App entry point for RMAnalyzer.
"""

import azure.functions as func
from rmanalyzer import controllers, storage

app = func.FunctionApp()


@app.route(route="upload", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def upload(req: func.HttpRequest) -> func.HttpResponse:
    """Receives a CSV, uploads to Blob, enqueues message, returns 202."""
    return controllers.handle_upload_async(req)


@app.queue_trigger(
    arg_name="msg", queue_name=storage.QUEUE_NAME, connection="StorageConnection"
)
def process_upload_queue(msg: func.QueueMessage) -> None:
    """Processes a queued upload message."""
    controllers.process_queue_item(msg)


@app.route(
    route="savings", methods=["GET", "POST"], auth_level=func.AuthLevel.ANONYMOUS
)
def handle_savings(req: func.HttpRequest) -> func.HttpResponse:
    """Handles getting and updating savings calculation data."""
    return controllers.handle_savings_dbrequest(req)

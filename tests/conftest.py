import os

# Set environment variables for tests immediately to support module-level imports
os.environ.setdefault("TABLE_SERVICE_URL", "http://127.0.0.1:10002")
os.environ.setdefault("BLOB_SERVICE_URL", "http://127.0.0.1:10000")
os.environ.setdefault("QUEUE_SERVICE_URL", "http://127.0.0.1:10001")
os.environ.setdefault("BLOB_CONTAINER_NAME", "test-container")
os.environ.setdefault("QUEUE_NAME", "test-queue")
os.environ.setdefault("TRANSACTIONS_TABLE", "test-transactions")
os.environ.setdefault("SAVINGS_TABLE", "test-savings")
os.environ.setdefault("PEOPLE_TABLE", "test-people")
os.environ.setdefault("AzureWebJobsStorage", "UseDevelopmentStorage=true")
os.environ.setdefault("FUNCTIONS_WORKER_RUNTIME", "python")
os.environ.setdefault(
    "COMMUNICATION_SERVICES_ENDPOINT", "https://test.communication.azure.com"
)
os.environ.setdefault("SENDER_EMAIL", "test-sender@example.com")

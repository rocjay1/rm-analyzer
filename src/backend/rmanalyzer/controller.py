"""
Controllers for handling application logic.
"""

import base64
import json
import logging
import os
from datetime import datetime, date, timedelta
from decimal import Decimal
from http import HTTPStatus

import azure.functions as func
from rmanalyzer import services
from rmanalyzer.models import (
    Group,
    Person,
    Account,
    Transaction,
    Category,
    IgnoredFrom,
    CreditCard,
)

from rmanalyzer.utils import get_transactions

__all__ = ["controller"]

logger = logging.getLogger(__name__)


# Limit file size to 10MB to prevent DoS
MAX_FILE_SIZE = 10 * 1024 * 1024


class Controller:
    """
    Controller for handling application logic and dependency injection.

    Initialized Services:
        db_service: Services for database interactions.
        blob_service: Services for blob storage operations.
        queue_service: Services for queue operations.
        email_service: Services for sending emails.
        email_renderer: Helper for rendering email content.
    """

    def __init__(self) -> None:
        # Instantiate Services
        # We do this at instance level (singleton) to cache clients
        self.db_service = services.DatabaseService()
        self.blob_service = services.BlobService()
        self.queue_service = services.QueueService()
        self.email_service = services.EmailService()
        self.email_renderer = services.EmailRenderer()

    def _get_user_email(self, req: func.HttpRequest) -> str | None:
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
        self,
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

    def handle_upload_async(self, req: func.HttpRequest) -> func.HttpResponse:
        """
        Receives a CSV, uploads it to Blob Storage, and queues a processing message.
        Returns 202 Accepted.
        """
        logging.info("Processing async upload request.")

        if not self._get_user_email(req):
            return func.HttpResponse(
                "Unauthorized", status_code=HTTPStatus.UNAUTHORIZED
            )

        try:
            # Extract File
            filename, content, error_resp = self._get_uploaded_file_content(req)
            if error_resp:
                return error_resp

            # Upload to Blob Storage
            # Generate a unique name to avoid overwrites
            base_name = os.path.basename(filename)
            blob_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{base_name}"

            blob_url = self.blob_service.upload_csv(blob_name, content)
            logging.info("Uploaded blob: %s", blob_url)

            # Enqueue Message
            self.queue_service.enqueue_message({"blob_name": blob_name})
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

    def process_queue_item(self, msg: func.QueueMessage) -> None:
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

            # Download CSV
            csv_content = self.blob_service.download_csv(blob_name)

            # Analysis
            transactions, errors = get_transactions(csv_content)

            # Retrieve People from DB
            people_data = self.db_service.get_all_people()
            members = [Person.from_config(p) for p in people_data]

            if errors and len(transactions) == 0:
                logging.error("CSV Validation Errors: %s", errors)

                # Send Error Email
                recipients = [p.email for p in members]
                self.email_service.send_error_email(recipients, errors)
                return

            # Save to DB
            try:
                # save_transactions now returns ONLY the transactions that were newly inserted
                # This handles the deduplication of file uploads.
                new_transactions = self.db_service.save_transactions(transactions)
                logging.info("Saved %d new transactions.", len(new_transactions))

                # Update Credit Card Balances
                # We only want to update balances for NEW transactions.
                # Additionally, we should check if the transaction is "covered" by a manual reconciliation.

                # Pre-fetch cards to check reconciliation dates
                cards = {
                    c.account_number: c for c in self.db_service.get_credit_cards()
                }

                card_updates = {}
                for t in new_transactions:
                    # Check if card exists and if transaction is after reconciliation
                    if t.account_number in cards:
                        card = cards[t.account_number]
                        if card.last_reconciled and t.date < card.last_reconciled:
                            logging.info(
                                "Skipping balance update for old transaction %s on card %s (Reconciled: %s)",
                                t.date,
                                card.name,
                                card.last_reconciled,
                            )
                            continue

                    if t.account_number not in card_updates:
                        card_updates[t.account_number] = Decimal("0.0")

                    card_updates[t.account_number] += t.amount

                for acc_num, delta in card_updates.items():
                    self.db_service.update_card_balance(acc_num, delta)

            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.error("Failed to save transactions or update cards: %s", e)

            # Email
            group = Group(members)
            group.add_transactions(transactions)

            if not any(p.transactions for p in group.members):
                logging.warning("No valid transactions found for configured accounts.")
                return

            body = self.email_renderer.render_body(group, errors=errors)
            subject = self.email_renderer.render_subject(group)
            recipients = [p.email for p in group.members]

            self.email_service.send_email(recipients, subject, body)

            logging.info("Processing complete for %s", blob_name)

        except Exception as e:
            logging.error("Error processing queue item: %s", e)
            # Raising exception ensures the message goes to poison queue after retries
            raise

    def _handle_savings_get(
        self, _: func.HttpRequest, month: str, user_email: str
    ) -> func.HttpResponse:
        """Helper for GET savings request."""
        data = self.db_service.get_savings(month, user_email)
        if data is None:
            return func.HttpResponse("Not Found", status_code=HTTPStatus.NOT_FOUND)

        return func.HttpResponse(
            json.dumps(data),
            mimetype="application/json",
            status_code=HTTPStatus.OK,
        )

    def _handle_savings_post(
        self, req: func.HttpRequest, month: str, user_email: str
    ) -> func.HttpResponse:
        """Helper for POST savings request."""
        try:
            req_body = req.get_json()
        except ValueError:
            return func.HttpResponse("Invalid JSON", status_code=HTTPStatus.BAD_REQUEST)

        target_month = req_body.get("month", month)

        # Basic validation
        if "startingBalance" not in req_body:
            return func.HttpResponse(
                "Missing required fields", status_code=HTTPStatus.BAD_REQUEST
            )

        self.db_service.save_savings(target_month, req_body, user_email)
        return func.HttpResponse("Saved successfully", status_code=HTTPStatus.OK)

    def handle_savings_dbrequest(self, req: func.HttpRequest) -> func.HttpResponse:
        """Handles getting and updating savings calculation data."""
        logging.info("Processing savings request.")

        user_email = self._get_user_email(req)
        if not user_email:
            return func.HttpResponse(
                "Unauthorized", status_code=HTTPStatus.UNAUTHORIZED
            )

        try:
            # Default month to current month if not provided
            current_month = datetime.now().strftime("%Y-%m")
            month = req.params.get("month", current_month)

            if req.method == "GET":
                return self._handle_savings_get(req, month, user_email)

            if req.method == "POST":
                return self._handle_savings_post(req, month, user_email)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Error in savings handler: %s", e)
            return func.HttpResponse(
                f"Internal Error: {str(e)}",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return func.HttpResponse(
            "Method not supported", status_code=HTTPStatus.METHOD_NOT_ALLOWED
        )

    def handle_cards(self, req: func.HttpRequest) -> func.HttpResponse:
        """
        Handles GET/POST/PUT for Credit Cards.
        GET: List all cards.
        POST: Create/Update a card config.
        PUT: Update card balance (manual adjustment or statement update).
        """
        logging.info("Processing cards request.")
        user_email = self._get_user_email(req)
        if not user_email:
            return func.HttpResponse(
                "Unauthorized", status_code=HTTPStatus.UNAUTHORIZED
            )

        try:
            if req.method == "GET":
                cards = self.db_service.get_credit_cards()
                # Convert to dicts
                cards_data = [
                    {
                        "id": c.id,
                        "name": c.name,
                        "account_number": c.account_number,
                        "credit_limit": float(c.credit_limit),
                        "due_day": c.due_day,
                        "statement_balance": float(c.statement_balance),
                        "current_balance": float(c.current_balance),
                        "utilization": float(c.utilization),
                        "target_payment": float(c.target_payment),
                        "last_reconciled": (
                            c.last_reconciled.isoformat() if c.last_reconciled else None
                        ),
                    }
                    for c in cards
                ]
                return func.HttpResponse(
                    json.dumps(cards_data),
                    mimetype="application/json",
                    status_code=HTTPStatus.OK,
                )

            if req.method == "POST":
                # Create/Update Configuration
                try:
                    body = req.get_json()
                    card = CreditCard(
                        id=body.get("id", str(body.get("account_number"))),
                        name=body["name"],
                        account_number=int(body["account_number"]),
                        credit_limit=Decimal(str(body["credit_limit"])),
                        due_day=int(body["due_day"]),
                        statement_balance=Decimal(
                            str(body.get("statement_balance", 0))
                        ),
                        current_balance=Decimal(str(body.get("current_balance", 0))),
                        last_reconciled=date.today(),
                    )
                    self.db_service.save_credit_card(card)
                    return func.HttpResponse(
                        "Card saved successfully", status_code=HTTPStatus.OK
                    )
                except (ValueError, KeyError) as e:

                    return func.HttpResponse(
                        f"Invalid Data: {e}", status_code=HTTPStatus.BAD_REQUEST
                    )

            if req.method == "PUT":
                # Reject PUT for now
                return func.HttpResponse(
                    "Use POST to update card.",
                    status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                )

        except Exception as e:
            logging.error("Error in cards handler: %s", e)
            return func.HttpResponse(
                f"Internal Error: {str(e)}",
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

        return func.HttpResponse(
            "Method not supported", status_code=HTTPStatus.METHOD_NOT_ALLOWED
        )

    def check_reminders(self) -> None:
        """
        daily check for credit card payment due dates.
        Sends email if due date is approaching (e.g., 3 days before).
        """
        logging.info("Checking for credit card reminders.")
        cards = self.db_service.get_credit_cards()
        today = date.today()

        reminders = []
        for card in cards:
            # Simple check: if due day is close
            # Handle month wrap?
            # Due Day is basically Day of Month.
            # Create a date for this month's due date
            try:
                due_date_this_month = today.replace(day=card.due_day)
            except ValueError:
                # e.g. due day 31 in Feb -> skip or check end of month
                continue

            # If due date passed, check next month? Or just check if today + 3 == due_date
            # Simple logic: target = today + 3 days
            target_date = today + timedelta(days=3)

            if target_date.day == card.due_day:
                # Calculate amount to pay
                to_pay = card.target_payment
                if to_pay > 0:
                    reminders.append(
                        {
                            "card": card.name,
                            "amount": to_pay,
                            "due_date": target_date.strftime("%Y-%m-%d"),
                        }
                    )

        if reminders:
            logging.info("Sending reminders for %d cards.", len(reminders))
            # Send email
            # We need a generic email method or update email_renderer
            # For now, just log or send simple email if email_service supports it.
            # EmailService has send_email(recipients, subject, body)
            # We need recipients. Get all people?
            people = self.db_service.get_all_people()
            recipients: list[str] = [
                str(p.get("Email")) for p in people if p.get("Email")
            ]

            subject = "Credit Card Payment Reminders"
            body = "<h2>Upcoming Payments</h2><ul>"
            for r in reminders:
                body += f"<li><b>{r['card']}</b>: Pay <b>${r['amount']:.2f}</b> by {r['due_date']}</li>"
            body += "</ul>"

            if recipients:
                self.email_service.send_email(recipients, subject, body)
        else:
            logging.info("No reminders to send.")

    def handle_sync_data(self, req: func.HttpRequest) -> func.HttpResponse:
        """
        Handles syncing accounts and transactions from the extension.
        Expects JSON payload with 'accounts' and 'transactions'.
        Auth: Checks for 'x-user-email' header.
        """
        logging.info("Processing sync request.")

        # For API Key auth, reasonable to trust a specific header for identity
        user_email = req.headers.get("x-user-email")
        if not user_email:
            return func.HttpResponse(
                "Missing 'x-user-email' header", status_code=HTTPStatus.BAD_REQUEST
            )

        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse("Invalid JSON", status_code=HTTPStatus.BAD_REQUEST)

        try:
            # Process Accounts
            accounts_data = body.get("accounts", [])
            accounts = []
            for acc in accounts_data:
                accounts.append(
                    Account(
                        id=str(acc["id"]),
                        name=acc["name"],
                        mask=acc.get("mask", ""),
                        institution=acc.get("institution", ""),
                        current_balance=Decimal(str(acc["current_balance"])),
                        credit_limit=Decimal(str(acc.get("credit_limit", 0))),
                        type=acc.get("type", "unknown"),
                    )
                )

            self.db_service.upsert_accounts(accounts, user_email)

            # Process Transactions
            # Note: Extension should send formatted transactions, but we map them here.
            trans_data = body.get("transactions", [])
            transactions = []
            for t in trans_data:
                # Basic category mapping or default
                # Extension might send raw text, we map to Category.OTHER for now
                # or try to match if valid.
                cat_val = t.get("category", "Other")
                try:
                    category = Category(cat_val)
                except ValueError:
                    category = Category.OTHER

                transactions.append(
                    Transaction(
                        date=date.fromisoformat(t["date"]),  # YYYY-MM-DD
                        name=t["name"],
                        account_number=int(
                            t.get("account_number", 0)
                        ),  # might use hash of ID if number not available
                        amount=Decimal(str(t["amount"])),
                        category=category,
                        ignore=IgnoredFrom.NOTHING,
                    )
                )

            self.db_service.save_transactions(transactions)

            return func.HttpResponse(
                f"Synced {len(accounts)} accounts and {len(transactions)} transactions.",
                status_code=HTTPStatus.OK,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.error("Error syncing data: %s", e)
            return func.HttpResponse(
                f"Sync Error: {str(e)}", status_code=HTTPStatus.INTERNAL_SERVER_ERROR
            )


# Singleton instance
controller = Controller()

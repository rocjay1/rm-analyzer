# Architecture Documentation

## 1. Overview
<!-- Provide a high-level summary of the system's purpose and goals. -->
This document describes the architecture of the `rm-analyzer` system, which is designed to analyze transactions and generate reports.

## 2. System Context
<!-- Describe how the system fits into the larger environment. Who are the users? What external systems does it interact with? -->
* **Users**: [e.g., Financial Analysts, Admins]
* **External Systems**: [e.g., Email Provider (SendGrid/SMTP), Identity Provider (Entra ID), Storage (Azure Blob)]

## 3. Architecture Diagrams

### 3.1 High-Level Design
<!-- Insert a diagram or description of the high-level components. -->
* **Frontend**: Single Page Application (Azure Static Web Apps)
* **Backend**: Serverless Functions (Azure Functions Flex Consumption, Python 3.11+)
* **Database**: Azure Table Storage (Transactions, Savings data)
* **Storage**: Azure Blob Storage (CSV uploads)
* **Messaging**: Azure Communication Services (Email notifications)

### 3.2 Data Flow
<!-- Describe how data moves through the system. -->
1. **Upload**: User uploads a bank CSV via the Frontend.
2. **Ingest**: Backend HTTP Trigger (`handle_upload_async`) saves the file to Blob Storage and queues a message.
3. **Process**: Backend Queue Trigger (`process_queue_item`) picks up the message:
    * Downloads the CSV from Blob Storage.
    * Parses transactions and categorizes them.
    * Saves transactions to Azure Table Storage.
    * Calculates splits and debts.
4. **Notify**: Backend sends a summary email via Azure Communication Services.
5. **Report**: User views savings and transaction data on the Frontend, fetched via HTTP APIs (`handle_savings_dbrequest`).

## 4. Components

### 4.1 Frontend

* **Tech Stack**: HTML/JS (Vanilla), Azure Static Web Apps, CSS (Variables/Flexbox)
* **Responsibilities**:
  * File upload interface.
  * Savings visualization.
  * Secure authentication via Azure Static Web Apps Auth.

### 4.2 Backend

* **Tech Stack**: Python, Azure Functions (Flex Consumption)
* **Key Modules**:
  * `rmanalyzer.controllers`: HTTP and Queue triggers / orchestration logic.
  * `rmanalyzer.models`: Core domain logic (Transactions, People, Groups) implemented as Python dataclasses.
  * `rmanalyzer.db`: `DatabaseService` for Azure Table Storage (Transactions, Savings, People).
  * `rmanalyzer.email`: `EmailRenderer` and `EmailService` for ACS Email.
  * `rmanalyzer.storage`: `BlobService` and `QueueService` for Azure Storage.
  * `rmanalyzer.utils`: Shared utilities for CSV parsing, date handling, and formatting.

### 4.3 Infrastructure

* **IaC**: Terraform
* **Resources**:
  * **Resource Group**: Logical container.
  * **Storage Account**: Blobs (uploads), Queues (messaging), Tables (data).
  * **Function App**: Flex Consumption plan (Linux).
  * **App Insights**: Monitoring and logging.
  * **Static Web App**: Frontend hosting.
  * **Communication Service**: Email delivery.

## 5. Data Model
<!-- Describe key data entities and schemas. -->
* **Transaction**: (Dataclass) Date, Name, Account Number, Amount (Decimal), Category (Enum), IgnoredFrom (Enum).
* **Person**: (Dataclass) Name, Email, Account Numbers, Transactions list.
* **Group**: (Dataclass) Collection of People, handles splitting logic.
* **Savings**: (Table Entity) Monthly summary and itemized savings entries.

## 6. Security & Compliance
<!-- Authentication, Authorization, Data Privacy. -->
* **Auth**: Azure App Service Authentication / GitHub OIDC.
* **Secrets**: Managed via Azure Key Vault / Environment Variables.

## 7. Deployment Strategy

* **CI/CD**: GitHub Actions (defined in `.github/workflows`).
* **Environments**: Dev, Prod.

## 8. Decision Log (ADRs)
<!-- Keep track of major architectural decisions here. -->
* [2026-01-26] - Migrated domain models (Transaction, Person, Group) to Python dataclasses for better type safety and immutability.
* [2026-01-26] - Refactored storage and database interactions into `Service` classes to encapsulate configuration (e.g., table/container names) and support dependency injection.
* [2026-01-26] - Consolidated parsing logic and helper functions into `rmanalyzer.utils` to improve maintainability and reuse across triggers.

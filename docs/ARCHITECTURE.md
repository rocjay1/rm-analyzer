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
* **Frontend**: Single Page Application (Static Web App)
* **Backend**: Serverless Functions (Azure Functions, Python)
* **Database/Storage**: [e.g., Azure Table Storage, Blob Storage]

### 3.2 Data Flow
<!-- Describe how data moves through the system. -->
1. User uploads file via Frontend.
2. Frontend calls Backend API.
3. Backend processes file and stores results.
4. ...

## 4. Components

### 4.1 Frontend

* **Tech Stack**: HTML/JS (Vanilla), Azure Static Web Apps
* **Responsibilities**: User interface for file upload and viewing reports.

### 4.2 Backend

* **Tech Stack**: Python, Azure Functions (HTTP Triggers)
* **Responsibilities**:
  * `rmanalyzer.transactions`: Parsing and processing logic.
  * `rmanalyzer.emailer`: Handling email notifications.
  * `rmanalyzer.azure_utils`: Integration with Azure services.

### 4.3 Infrastructure

* **IaC**: Terraform
* **Resources**: Function App, Storage Account, Static Web App, Key Vault.

## 5. Data Model
<!-- Describe key data entities and schemas. -->
* **Transaction**: [Fields: Date, Amount, Description...]
* **Report**: [Fields: ID, GeneratedDate, Status...]

## 6. Security & Compliance
<!-- Authentication, Authorization, Data Privacy. -->
* **Auth**: Azure App Service Authentication / GitHub OIDC.
* **Secrets**: Managed via Azure Key Vault / Environment Variables.

## 7. Deployment Strategy

* **CI/CD**: GitHub Actions (defined in `.github/workflows`).
* **Environments**: Dev, Prod.

## 8. Decision Log (ADRs)
<!-- Keep track of major architectural decisions here. -->
* [Date] - Chosen Python for backend due to library support for data analysis.
* [Date] - Chosen Terraform for consistent infrastructure management.

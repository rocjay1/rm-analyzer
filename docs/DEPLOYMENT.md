# Deployment Guide

This document outlines the steps to deploy the `rm-analyzer` infrastructure and applications to Azure.

## Prerequisites

- **Azure CLI**: For authentication and managing Azure resources.
- **Terraform 1.5+**: For Infrastructure as Code (IaC).
- **GitHub CLI (gh)**: For managing GitHub secrets and variables (optional but recommended).

## Infrastructure Setup (Terraform)

The infrastructure is defined in the `infra/` directory. It uses Azure Storage for the Terraform backend state.

### 1. Initialize Terraform

Navigate to the `infra` directory and initialize Terraform. You may need to provide backend configuration (storage account details) if not already configured.

```bash
cd infra
terraform init
```

### 2. Configure Variables

Create a `terraform.tfvars` file or pass variables via command line. Key variables include:

| Variable | Description |
| :--- | :--- |
| `project_name` | Base name for resources (default: `rmanalyzer`) |
| `location` | Azure region for primary resources (default: `eastus`) |
| `subscription_id` | Target Azure Subscription ID |
| `github_repo` | GitHub repository (`owner/repo`) for OIDC trust |
| `cloudflare_api_token` | **Sensitive**. Token for DNS/Zero Trust management |
| `account_id` | Cloudflare Account ID |
| `zone_id` | Cloudflare Zone ID |
| `zone_name` | Cloudflare Zone Name (e.g. `example.com`) |

### 3. Deploy

```bash
terraform apply
```

This will provision:

- **Resource Group**
- **Function App** (Flex Consumption Plan)
- **Static Web App**
- **Storage Account** & **Key Vault**
- **Communication Services** (Email)
- **GitHub OIDC Credentials** (Federated Identity)

## Configuration

The application relies on several Environment Variables and Secrets.

### Backend (Function App)

Managed automatically by Terraform, but key settings include:

- `COMMUNICATION_SERVICES_ENDPOINT`: For sending emails.
- `SENDER_EMAIL`: Verified sender address from Communication Services.
- `BLOB_SERVICE_URL`: Endpoint for Blob storage (e.g. `https://<account>.blob.core.windows.net/`).
- `QUEUE_SERVICE_URL`: Endpoint for Queue storage (e.g. `https://<account>.queue.core.windows.net/`).
- `TABLE_SERVICE_URL`: Endpoint for Table storage (e.g. `https://<account>.table.core.windows.net/`).
- `BLOB_CONTAINER_NAME`: Name of container for CSVs (defaults to `csv-uploads`).
- `QUEUE_NAME`: Name of the processing queue (defaults to `csv-processing`).
- `TRANSACTIONS_TABLE`: Table name for transaction data (defaults to `transactions`).
- `SAVINGS_TABLE`: Table name for savings data (defaults to `savings`).
- `PEOPLE_TABLE`: Table name for user/people data (defaults to `people`).
- `AzureWebJobsStorage`: Connection string for internal Function App operation.

### CI/CD Secrets

For GitHub Actions to deploy, the following secrets must be set in the repository (Terraform outputs some of these):

- `AZURE_CLIENT_ID`: Client ID of the User Assigned Identity for OIDC.
- `AZURE_TENANT_ID`: Azure Tenant ID.
- `AZURE_SUBSCRIPTION_ID`: Azure Subscription ID.
- `AZURE_STATIC_WEB_APPS_API_TOKEN`: Deployment token for the Static Web App.
- `AZURE_FUNCTION_APP_NAME`: Name of the Function App to deploy to.

## Continuous Integration & Deployment (CI/CD)

### 1. CI Pipeline (`ci.yml`)

- **Triggers**: Push/PR to `main`.
- **Jobs**:
  - Runs `black` (formatting), `isort` (imports), and `pylint` (linting).
  - Executes `pytest` execution for backend logic.

### 2. Deployment Pipeline (`azure-static-web-apps-*.yml`)

- **Triggers**: Pushing a tag starting with `v*` (e.g., `v1.0.0`).
- **Jobs**:
  - **Frontend**: Deploys the vanilla JS app to Azure Static Web Apps.
  - **Backend**: Deploys the Python code to the Azure Function App (Flex Consumption) using OIDC authentication.

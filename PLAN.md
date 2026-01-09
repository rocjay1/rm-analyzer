# Project Status & Plan

## Completed Work (Infrastructure & Migration)

We have successfully migrated the architecture from AWS Serverless to a secure, "Keyless" Azure Native stack.

### 1. Infrastructure (Terraform)
- **Zero-Key Security**: Implemented a fully identity-based architecture.
    - **Function App**: Uses System-Assigned Managed Identity for all connections (Storage, Email). removed `AzureWebJobsStorage` connection string in favor of `AzureWebJobsStorage__accountName`.
    - **Storage**: Restricted access via RBAC (`Blob Data Owner`, `Queue Data Contributor`, `Table Data Contributor`).
    - **Communication Services**: RBAC-based email sending (`Contributor` scoped to resource).
- **Authentication (Entra ID)**:
    - Automated App Registration creation with Terraform.
    - Enforced **Strict User Assignment** (`app_role_assignment_required = true`).
    - Solved circular dependency between App Registration (Redirect URI) and Static Web App (Hostname).
- **Frontend Hosting**:
    - Azure Static Web App (Standard SKU).
    - Auto-injection of Client ID/Secret for auth configuration.

### 2. Codebase Migration
- **Backend (Python)**:
    - Ported `function_app.py` to use Azure Functions v2 model.
    - Replaced AWS SES with `azure-communication-email`.
    - Removed S3 dependencies; logic now handles direct stream processing or identity-based blob access.
- **Frontend (JS/HTML)**:
    - Updated for Azure Static Web Apps Authentication (`/.auth/login/aad`).
    - Direct API calls to `/api/upload`.

### 3. Configuration
- **DEPLOYMENT.md**: comprehensive guide for deploying and securing the application.
- **Local Dev**: Configured `staticwebapp.config.json` and local role requirements.

---

## Upcoming Work (Business Logic & Validation)

The infrastructure is ready. The next phase focuses on verifying the ported business logic and ensuring the application runs correctly.

### 1. Business Logic Verification
- **Run Unit Tests**: Execute `tests_new/test_logic.py` to verify the core financial logic (grouping, math) works identically to the AWS version.
- **Edge Case Handling**: Ensure file parsing (CSV headers, data formats) is robust against the expected Azure input stream.
- **Email Formatting**: Verify the HTML email generation looks correct.

### 2. End-to-End Testing
- **Deployment**: User to run `terraform apply` and deploy code.
- **Integration Test**:
    1.  User logs in via Entra ID.
    2.  Uploads a CSV.
    3.  Backend processes file without storage keys.
    4.  Email is received via Azure Communication Services.

### 3. Cleanup & Optimization
- Review code for any lingering AWS references (boto3, etc.).
- Fine-tune Function App performance settings (Consumption plan warm-up if needed).

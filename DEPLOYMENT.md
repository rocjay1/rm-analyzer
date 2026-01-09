# RM Analyzer - Azure Migration (Entra ID Edition)

This project has been migrated from AWS Serverless to Azure Native (Functions + Static Web Apps), utilizing **Entra ID** and **Managed Identities** for maximum security.

## Security Highlights
- **Frontend Auth**: Static Web App requires Azure AD login.
- **Strict Access**: The App Registration is configured to **require user assignment**. Only users explicitly added to the application in Entra ID can log in.
- **Backend Auth**: Function App uses System-Assigned Managed Identity.
- **Keyless Access**: No access keys or connection strings are stored or used. Access is granted via RBAC roles (`Contributor` on Communication Services, plus `Storage Blob Data Owner`, `Queue Data Contributor`, and `Table Data Contributor` for the Function App).
- **Secure Traffic**: HTTPS-only, TLS 1.2+, and CORS restricted strictly to the frontend URL.

## Deployment Steps

### 1. Infrastructure (Terraform)
Initialize and apply the Terraform configuration.

```bash
cd infra
terraform init
terraform apply -var="subscription_id=<YOUR_SUB_ID>"
```

**Note the Outputs:**
- `tenant_id`: Your Azure Tenant ID.
- `function_app_name`: The name of your Function App.
- `static_web_app_url`: The URL of your frontend.

### 2. Configure Frontend
Update the frontend configuration with your Tenant ID to ensure correct authentication routing.

1. Open `src/frontend/staticwebapp.config.json`.
2. Replace `<YOUR_TENANT_ID>` with the `tenant_id` from the Terraform output.

### 3. Configure Backend
Update the local configuration file with your financial grouping details.

1. Open `src/backend/config.json`.
2. Update the `People`, `Owner`, and `SenderEmail` fields with your real data.

### 4. Grant Access (Crucial Step)
The infrastructure is secure by default. **No one (including you) can log in yet.**

1. Go to the [Azure Portal](https://portal.azure.com).
2. Navigate to **Microsoft Entra ID** -> **Enterprise applications**.
3. Search for **`rmanalyzer-frontend`** (remove the filters if you don't see it).
4. Select **Users and groups**.
5. Click **Add user/group** and add yourself and any other users who need access.

### 5. Backend Deployment
Deploy the Python Function App.

```bash
cd src/backend
func azure functionapp publish <FUNCTION_APP_NAME>
```

### 6. Frontend Deployment
Deploy the Static Web App.

```bash
cd src/frontend
swa deploy . --app-name <STATIC_WEB_APP_NAME>
```
*Note: If `swa deploy` fails, you may need to retrieve the deployment token from the Azure Portal (Static Web App -> Manage deployment token) and pass it with `--deployment-token <TOKEN>`.*

## Usage
1. Open the `static_web_app_url`.
2. Log in with your Entra ID account.
3. Select your transaction CSV file and click **Upload**.
4. The file is sent securely to the backend, analyzed, and the summary email is sent immediately.

## Local Development
To run locally, your developer account (Azure CLI) needs the same permissions as the Managed Identity.

1.  **Grant yourself roles**:
    *   `Contributor` on the **Communication Service** resource (to send emails).
    *   `Storage Blob Data Contributor` on the **Storage Account** (to test the audit upload, if enabled).
2.  **Run Backend**:
    ```bash
    cd src/backend
    func start
    ```
3.  **Run Frontend**:
    ```bash
    cd src/frontend
    swa start . --api-location http://localhost:7071
    ```
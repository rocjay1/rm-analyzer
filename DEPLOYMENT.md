# 🚀 RM-Analyzer Deployment Checklist

## 1. Prerequisites

- [x] Install **Azure CLI** and run `az login`.
- [x] Install **Terraform** (>= 1.5).
- [x] Ensure you have `Contributor` and `User Access Administrator` (or `Owner`) roles on the target subscription to manage Entra ID registrations.
- [x] Initialize Terraform: `cd infra && terraform init`.

## 2. Infrastructure Provisioning (Terraform)

- [x] Create a `terraform.tfvars` file or prepare environment variables:

    ```hcl
    subscription_id = "your-guid-here"
    project_name    = "rmanalyzer"
    location        = "eastus"
    ```

- [x] **Plan & Apply:**
  - [x] `terraform plan -out=main.tfplan`
  - [x] `terraform apply "main.tfplan"`
- [x] **Capture Outputs:** Note the `static_web_app_url`, `function_app_name`, and `tenant_id`.

## 3. Post-Infrastructure Manual Steps

- [x] **Email Domain Verification:**
  - Navigate to **Communication Services** > **Email** > **Domains** in the Azure Portal.
  - Check if the `AzureManagedDomain` status is "Verified". It can take 5–15 minutes for Azure to fully provision the managed domain.
- [x] **Entra ID User Assignment:**
  - Since `app_role_assignment_required = true` is set in `entra.tf`, you **must** manually assign users or groups to the Enterprise Application.
  - Go to **Microsoft Entra ID** > **Enterprise applications** > Search for `rmanalyzer-frontend`.
  - Select **Users and groups** > **Add user/group** and add yourself to gain login access.

## 4. Application Code Deployment

- [x] **Backend (Azure Functions):**
  - Install [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local).
  - Run from the root:

      ```bash
      cd src/backend
      func azure functionapp publish <YOUR_FUNCTION_APP_NAME_FROM_TERRAFORM>
      ```

- [x] **Frontend (Static Web App):**
  - The easiest way is using the [SWA CLI](https://azure.github.io/static-web-apps-cli/):

      ```bash
      cd src/frontend
      swa deploy --app-location . --env production --resource-group <RG_NAME> --app-name <SWA_NAME>
      ```

  - *Alternatively*: Configure a GitHub Action/Azure DevOps pipeline using the deployment token provided in the SWA resource in the Portal.

## 5. Security & Connectivity Verification

- [x] **Verify SWA Linkage:** In the portal, go to your **Static Web App** > **APIs**. Ensure your Function App appears as a "Linked" backend.
- [x] **Test Direct Access (Defense Check):**
  - Try to access `https://<YOUR-FUNC>.azurewebsites.net/api/heartbeat`.
  - It should return **401 Unauthorized** because only requests proxied via SWA are allowed.
- [x] **End-to-End Test:**
  - Navigate to the `static_web_app_url`.
  - Login via Entra ID (verify the redirect to `/.auth/login/aad/callback` works).
  - Perform a transaction analysis to ensure the frontend can call the backend.

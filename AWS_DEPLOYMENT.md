# AWS Infrastructure & Deployment Checklist for rm-analyzer

This document describes the required AWS resources, IAM permissions, and CI/CD secrets for deploying and running the `rm-analyzer` project using the Serverless Framework and GitHub Actions.

---

## 1. Required AWS Resources

### S3 Buckets
- **rm-analyzer-sheets-prd**: For uploading transaction CSVs (triggers Lambda).
- **Config bucket**: For storing the config JSON (must exist and be accessible by Lambda).

### SES (Simple Email Service)
- SES must be enabled in `us-east-1`.
- All sender and recipient emails must be verified (unless SES is out of sandbox).

### Lambda Function
- Created by Serverless Framework during deployment.
- Uses Python 3.13 runtime.

### CloudWatch Logs
- Automatically created by Lambda for logging and monitoring.

---

## 2. IAM Roles & Permissions

### Lambda Execution Role
- Managed policies attached (see `serverless.yml`):
  - `AmazonS3ReadOnlyAccess`
  - `AmazonSESFullAccess`
  - `AWSLambdaBasicExecutionRole`

### GitHub Actions Deploy User
- Needs permissions for CloudFormation, Lambda, S3, SES, IAM, and logs.
- Attach the following policy to the IAM user whose keys are in your GitHub repo secrets:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "lambda:*",
        "s3:*",
        "iam:PassRole",
        "iam:GetRole",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "ses:*",
        "logs:*"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## 3. GitHub Repository Secrets

Set these secrets in your GitHub repository:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- (Optional) `SERVERLESS_ACCESS_KEY` (if using Serverless Dashboard features)

---

## 4. Deployment & Operation Summary

- The Serverless Framework deploys the Lambda, IAM roles, and permissions as defined in `serverless.yml`.
- The Lambda is triggered by S3 `PUT` events to the `rm-analyzer-sheets-prd` bucket.
- The Lambda reads config from a separate S3 bucket and sends summary emails via SES.
- All logs are available in CloudWatch.

---

## 5. Troubleshooting

- Ensure all buckets exist before deployment.
- Verify SES is set up and emails are verified.
- Make sure IAM permissions are correct for both Lambda and deploy user.
- Check that GitHub secrets are set and valid.

---

For further details, see `serverless.yml` and the project README.

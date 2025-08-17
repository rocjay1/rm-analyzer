
# rm-analyzer

> **Disclaimer:**
>
> This project is currently archived and not actively maintained or deployed. It is resurfaced here for reference and inspiration, as it demonstrates some interesting ideas in AWS automation, Python modularity, and CI/CD. Feel free to explore, adapt, or build upon it, but be aware that the infrastructure and deployment pipeline may require updates before use in production.

## Overview

**rm-analyzer** is a Python project designed to automate the summarization of expense data and email reporting using AWS Lambda, S3, and SES. The project is fully type-checked, robustly tested, and features modern CI/CD for seamless deployment.

## Features

- **Modular Python Package**: All business logic is organized in the `rmanalyzer/` package, with clear separation of models, configuration, AWS utilities, transaction processing, and email generation.
- **AWS Lambda Ready**: The entry point (`main.py`) is a thin Lambda handler that leverages the package modules. Designed for S3-triggered execution.
- **Type Safety**: Uses `mypy` and type hints throughout for maximum reliability.
- **Comprehensive Testing**: Includes both unit and edge case tests (`tests/`), using `unittest` and `moto` for AWS mocking.
- **Modern CI/CD**: GitHub Actions workflow runs tests, type checks, and deploys to AWS Lambda via the Serverless Framework on every push to `main`.
- **Easy Configuration**: Reads summary configuration from S3, validates it, and assigns transactions to people and categories.
- **Automated Emailing**: Generates and sends summary emails via AWS SES.

## How It Works

1. **Upload Data**: Export your transaction data as CSV from your financial app and upload it to the designated S3 bucket.
2. **Lambda Trigger**: The S3 `PUT` event triggers the Lambda function (`main.py`).
3. **Config Loading**: The function loads and validates configuration (people, accounts, emails, owner) from a separate S3 bucket.
4. **Transaction Processing**: Transactions are parsed, assigned to people, and summarized by category.
5. **Email Generation**: A summary email is constructed and sent to the configured recipients using AWS SES.

### Example CSV Input

```csv
Date,Original Date,Account Type,Account Name,Account Number,Institution Name,Name,Custom Name,Amount,Description,Category,Note,Ignored From,Tax Deductible
2023-08-31,2023-08-31,Credit Card,SavorOne,1313,Capital One,MADCATS DANCE,,150,MADCATS DANCE,Entertainment & Rec.,,,
2023-09-04,2023-09-04,Credit Card,CREDIT CARD,1234,Chase,TIKICAT BAR,,12.66,TIKICAT BAR,Dining & Drinks,,,
2023-09-12,2023-09-12,Cash,Spending Account,2121,Ally Bank,FISH MARKET,,47.71,FISH MARKET,Groceries,,,
```

### Example Config (JSON)

```json
{
  "People": [
     { "Name": "George", "Accounts": [1234], "Email": "boygeorge@gmail.com" },
     { "Name": "Tootie", "Accounts": [1313], "Email": "tuttifruity@hotmail.com" }
  ],
  "Owner": "bebas@gmail.com"
}
```

## Project Structure

```
main.py                  # Lambda entry point
rmanalyzer/              # Modular package (models, config, aws_utils, transactions, emailer)
tests/                   # Unit and edge case tests
requirements.txt         # Runtime dependencies
test_requirements.txt    # Test/development dependencies
serverless.yml           # Serverless Framework config
.github/workflows/       # CI/CD pipeline
.gitignore               # Ignores venv, cache, etc.
```

## Development & Testing

1. **Setup**: Use Python 3.13+ and create a virtual environment.
2. **Install dependencies**:
    ```sh
    pip install -r requirements.txt -r test_requirements.txt
    ```
3. **Run tests**:
    ```sh
    python -m unittest discover tests
    ```
4. **Type check**:
    ```sh
    mypy rmanalyzer
    ```

## CI/CD & Deployment

- On every push to `main`, GitHub Actions runs all tests, type checks, and (if successful) deploys the Lambda using the Serverless Framework.
- Lambda runs on Python 3.13 and only includes the necessary code and dependencies.

## Key Technologies

- **Python 3.13**
- **AWS Lambda, S3, SES**
- **Serverless Framework**
- **GitHub Actions**
- **mypy, unittest, moto, boto3, typeguard, yattag**

## References

- [mypy](https://mypy.readthedocs.io/en/stable/getting_started.html)
- [moto](https://docs.getmoto.org/en/latest/docs/getting_started.html)
- [unittest](https://realpython.com/python-testing/)
- [Serverless Framework](https://www.serverless.com/framework/docs/tutorial)
- [yattag](https://www.yattag.org/#tutorial)
- [typeguard](https://typeguard.readthedocs.io/en/stable/)

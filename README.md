Daily Tech Brief
================

A serverless transaction analysis and reporting tool designed to automate monthly financial tracking and shared expense reporting.

Features
--------

- **CSV Transaction Parsing**: Automatically parses bank transaction exports (CSV) and categorizes spending.
- **Smart Categorization**: Categorizes transactions into Dining, Groceries, Pets, Bills, Travel, etc.
- **Expense Splitting**: Calculates shared expenses and determines debts between group members.
- **Savings Tracking**: tracks monthly savings data for visualization.
- **Automated Reports**: Generates and sends summarized expense reports via email.
- **Serverless Architecture**: Built on Azure Functions (Flex Consumption) and Azure Static Web Apps for cost-effective scalability.

Documentation
-------------

- [System Architecture](docs/ARCHITECTURE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

Local Development
-----------------

1. **Prerequisites**: Ensure you have Python 3.11+, Node.js, Azure Functions Core Tools, and Azurite installed.
2. **Setup**: Run `./setup_local.sh` to install python dependencies and setup the environment.
3. **Run**: Execute `./run_local.sh` to start the local development environment:
    - **Frontend**: <http://localhost:4280>
    - **Backend API**: <http://localhost:7071>
    - **Blob Storage Emulator**: <http://127.0.0.1:10000>


# Refactored RMAnalyzer Lambda entry point
from typing import Any
from rmanalyzer.aws_utils import get_s3_content
from rmanalyzer.config import get_config_from_str, validate_config
from rmanalyzer.transactions import get_transactions
from rmanalyzer.models import Person, Group
from rmanalyzer.emailer import SummaryEmail

CONFIG_BUCKET, CONFIG_KEY = "rmanalyzer-config", "config.json"

def get_members(people_config: list[dict]) -> list[Person]:
    return [
        Person(
            p["Name"],
            p["Email"],
            p["Accounts"],
            []
        )
        for p in people_config
    ]

def lambda_handler(event: Any, context: Any) -> None:
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = event["Records"][0]["s3"]["object"]["key"]

    # Read data from buckets
    config_str = get_s3_content(CONFIG_BUCKET, CONFIG_KEY)
    config = get_config_from_str(config_str)
    validate_config(config)
    csv_content = get_s3_content(bucket, key)
    transactions = get_transactions(csv_content)

    # Construct group and add transactions
    members = get_members(config["People"])
    group = Group(members)
    group.add_transactions(transactions)

    # Construct and send email
    email = SummaryEmail(config["Owner"], [p.email for p in group.members])
    email.add_body(group)
    email.add_subject(group)
    email.send()

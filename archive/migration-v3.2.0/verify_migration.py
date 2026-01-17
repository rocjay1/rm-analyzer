#!/usr/bin/env python3
import json
import logging
import os
import sys

# Add src/backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src", "backend"))

from rmanalyzer import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def verify():
    people = db.get_all_people()
    logger.info("Retrieved %d people from DB", len(people))
    for p in people:
        logger.info(
            "Person: %s, Email: %s, Accounts: %s", p["Name"], p["Email"], p["Accounts"]
        )

    if len(people) == 0:
        logger.error("No people found! Migration might have failed.")
        sys.exit(1)


if __name__ == "__main__":
    verify()

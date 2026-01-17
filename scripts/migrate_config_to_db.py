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

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "backend", "config.json"
)


def migrate():
    if not os.path.exists(CONFIG_PATH):
        logger.error("Config file not found at %s", CONFIG_PATH)
        return

    logger.info("Loading config from %s", CONFIG_PATH)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    people = config.get("People", [])
    logger.info("Found %d people to migrate", len(people))

    for person in people:
        logger.info("Migrating %s (%s)", person["Name"], person["Email"])
        try:
            db.save_person(person)
            logger.info("Successfully saved %s", person["Name"])
        except Exception as e:
            logger.error("Failed to save %s: %s", person["Name"], e)


if __name__ == "__main__":
    migrate()

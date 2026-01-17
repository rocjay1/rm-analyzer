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
    config = None

    # 1. Try Environment Variable (CI / Production)
    env_config = os.environ.get("APP_CONFIG_JSON")
    if env_config:
        try:
            config = json.loads(env_config)
            logger.info("Loaded config from APP_CONFIG_JSON")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse APP_CONFIG_JSON: %s", e)

    # 2. Try File (Local Dev)
    if config is None:
        if os.path.exists(CONFIG_PATH):
            logger.info("Loading config from %s", CONFIG_PATH)
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
        else:
            logger.error(
                "Config file not found at %s and APP_CONFIG_JSON not set", CONFIG_PATH
            )
            return

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

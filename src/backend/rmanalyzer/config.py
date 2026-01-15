"""
Configuration management for RMAnalyzer.
"""

import json
import logging

from typeguard import TypeCheckError, check_type

__all__ = ["validate_config", "get_config_from_str"]

logger = logging.getLogger(__name__)


def validate_config(config: dict) -> None:
    """Validate the structure and types of the configuration dictionary."""
    try:
        people = config["People"]
        check_type(people, list[dict])
        for p in people:
            check_type(p["Name"], str)
            check_type(p["Email"], str)
            check_type(p["Accounts"], list[int])

    except (KeyError, TypeCheckError) as ex:
        logger.error("Invalid configuration: %s", ex)
        raise


def get_config_from_str(config_str: str) -> dict:
    """Parse configuration from a JSON string."""
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as ex:
        logger.error("Error loading config: %s", ex)
        raise

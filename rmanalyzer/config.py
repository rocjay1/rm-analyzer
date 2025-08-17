
"""
Configuration loading and validation for RMAnalyzer.

This module provides helpers for loading and validating configuration data.
"""
import json
import logging
from typeguard import check_type, TypeCheckError

__all__ = ["validate_config", "get_config_from_str"]

logger = logging.getLogger(__name__)

def validate_config(config: dict) -> None:
    """Validate the configuration dictionary for required structure and types."""
    try:
        people = config["People"]
        check_type(people, list[dict])
        for p in people:
            check_type(p["Name"], str)
            check_type(p["Email"], str)
            check_type(p["Accounts"], list[int])
        check_type(config["Owner"], str)
    except (KeyError, TypeCheckError) as ex:
        logger.error("Invalid configuration: %s", ex)
        raise

def get_config_from_str(config_str: str) -> dict:
    """Parse a JSON configuration string into a dictionary."""
    try:
        return json.loads(config_str)
    except json.JSONDecodeError as ex:
        logger.error("Error loading config: %s", ex)
        raise

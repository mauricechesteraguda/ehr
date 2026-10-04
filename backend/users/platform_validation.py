"""type-10042026-Maurice: Safe offline platform contract validation seam."""

from __future__ import annotations

import json
import logging
from typing import Any

from .tracing import trace_function


logger = logging.getLogger("ehr.platform_validation")


@trace_function
def validate_manifest_text(text: str) -> dict[str, Any]:
    """type-10042026-Maurice: Validate JSON input without exposing payload or parser details."""
    try:
        manifest = json.loads(text)
    except (TypeError, ValueError) as error:
        logger.info("platform.validation.invalid_manifest")
        raise ValueError("invalid_manifest") from error
    if not isinstance(manifest, dict) or manifest.get("schema") != "ehr.platform.tool-versions.v1":
        logger.info("platform.validation.invalid_manifest")
        raise ValueError("invalid_manifest")
    return manifest


@trace_function
def validate_changed_paths(changed_paths: list[str]) -> dict[str, str]:
    """type-10042026-Maurice: Return stable evidence for a clean offline change set."""
    if not changed_paths:
        logger.info("platform.validation.no_applicable_changes")
        return {"status": "no_applicable_changes", "deployment": "not_claimed"}
    logger.info("platform.validation.pending_changes")
    return {"status": "applicable_changes", "deployment": "not_claimed"}

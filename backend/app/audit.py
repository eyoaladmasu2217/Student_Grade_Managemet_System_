import json
import logging

logger = logging.getLogger("sgms.security")


def log_security_event(event: str, outcome: str, **details: object) -> None:
    safe_details = {
        key: str(value).replace("\n", "\\n")[:200] for key, value in details.items()
    }
    logger.log(
        logging.WARNING if outcome == "failure" else logging.INFO,
        "SECURITY event=%s outcome=%s details=%s",
        event,
        outcome,
        json.dumps(safe_details, sort_keys=True),
    )

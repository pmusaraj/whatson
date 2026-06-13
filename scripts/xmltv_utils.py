#!/usr/bin/env python3
"""Small XMLTV parsing helpers shared by validation/reporting scripts."""

from __future__ import annotations

from datetime import datetime, timezone

XMLTV_TIME_FORMAT = "%Y%m%d%H%M%S %z"


def parse_xmltv_time(value: str) -> datetime:
    """Parse an XMLTV timestamp and return a UTC-aware datetime."""
    if not value:
        raise ValueError("missing XMLTV time")
    return datetime.strptime(value, XMLTV_TIME_FORMAT).astimezone(timezone.utc)


def iso_z(value: datetime) -> str:
    """Format a datetime as second-precision UTC ISO-8601 with a Z suffix."""
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

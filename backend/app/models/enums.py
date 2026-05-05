from __future__ import annotations

import enum


class WorkItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class SeverityLevel(str, enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


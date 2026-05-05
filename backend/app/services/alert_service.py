from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger
from app.core.settings import settings
from app.models.enums import SeverityLevel
from app.models.work_item import WorkItem


logger = get_logger(__name__)


class AlertStrategy(ABC):
    @abstractmethod
    async def send_alert(self, work_item: WorkItem) -> None:  # pragma: no cover
        raise NotImplementedError


class EmailAlertStrategy(AlertStrategy):
    async def send_alert(self, work_item: WorkItem) -> None:
        logger.info(
            "Email alert sent",
            extra={
                "work_item_id": str(work_item.id),
                "component_id": work_item.component_id,
                "severity": work_item.severity.value,
                "title": work_item.title,
            },
        )


class SlackAlertStrategy(AlertStrategy):
    async def send_alert(self, work_item: WorkItem) -> None:
        logger.info(
            "Slack alert sent",
            extra={
                "work_item_id": str(work_item.id),
                "component_id": work_item.component_id,
                "severity": work_item.severity.value,
                "title": work_item.title,
            },
        )


class CombinedAlertStrategy(AlertStrategy):
    def __init__(self) -> None:
        self._email = EmailAlertStrategy()
        self._slack = SlackAlertStrategy()

    async def send_alert(self, work_item: WorkItem) -> None:
        await asyncio.gather(self._email.send_alert(work_item), self._slack.send_alert(work_item))


class AlertService:
    """
    Strategy selection is driven by a severity->strategy map.
    Extensible: add strategies by registering a new key in `_STRATEGY_REGISTRY`.
    """

    _STRATEGY_REGISTRY: dict[str, type[AlertStrategy]] = {
        "email": EmailAlertStrategy,
        "slack": SlackAlertStrategy,
        "combined": CombinedAlertStrategy,
    }

    def __init__(self, severity_map: dict[str, str] | None = None) -> None:
        self._severity_map = severity_map or default_severity_strategy_map()

    def get_strategy(self, work_item: WorkItem) -> AlertStrategy:
        key = self._severity_map.get(work_item.severity.value, "email")
        cls = self._STRATEGY_REGISTRY.get(key)
        if cls is None:
            logger.warning("Unknown alert strategy key; defaulting to email", extra={"key": key})
            cls = EmailAlertStrategy
        return cls()

    async def send_alert(self, work_item: WorkItem) -> None:
        strategy = self.get_strategy(work_item)
        logger.info(
            "Alert triggered",
            extra={"work_item_id": str(work_item.id), "severity": work_item.severity.value, "strategy": type(strategy).__name__},
        )
        await strategy.send_alert(work_item)


def default_severity_strategy_map() -> dict[str, str]:
    """
    Configurable via `IMS_ALERT_STRATEGY_MAP` (JSON), e.g.:
      {"P0":"combined","P1":"slack","P2":"email"}
    """
    raw = getattr(settings, "alert_strategy_map_json", "")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except Exception:
            logger.exception("Invalid IMS_ALERT_STRATEGY_MAP; using defaults")
    return {"P0": "combined", "P1": "slack", "P2": "email"}


async def send_alert_non_blocking(work_item: WorkItem) -> None:
    """Fire-and-forget wrapper (intended for create_task)."""
    try:
        await AlertService().send_alert(work_item)
    except Exception:
        logger.exception("Alert send failed", extra={"work_item_id": str(work_item.id)})


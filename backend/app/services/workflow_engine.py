from __future__ import annotations

from abc import ABC

from app.core.logging import get_logger
from app.models.enums import WorkItemStatus


logger = get_logger(__name__)


class InvalidTransitionError(ValueError):
    def __init__(self, from_status: WorkItemStatus, to_status: WorkItemStatus):
        super().__init__(f"Cannot move from {from_status.value} to {to_status.value}")
        self.from_status = from_status
        self.to_status = to_status


class BaseState(ABC):
    status: WorkItemStatus

    def move_to_investigating(self) -> WorkItemStatus:
        raise InvalidTransitionError(self.status, WorkItemStatus.INVESTIGATING)

    def move_to_resolved(self) -> WorkItemStatus:
        raise InvalidTransitionError(self.status, WorkItemStatus.RESOLVED)

    def move_to_closed(self) -> WorkItemStatus:
        raise InvalidTransitionError(self.status, WorkItemStatus.CLOSED)


class OpenState(BaseState):
    status = WorkItemStatus.OPEN

    def move_to_investigating(self) -> WorkItemStatus:
        return WorkItemStatus.INVESTIGATING


class InvestigatingState(BaseState):
    status = WorkItemStatus.INVESTIGATING

    def move_to_resolved(self) -> WorkItemStatus:
        return WorkItemStatus.RESOLVED


class ResolvedState(BaseState):
    status = WorkItemStatus.RESOLVED

    def move_to_closed(self) -> WorkItemStatus:
        return WorkItemStatus.CLOSED


class ClosedState(BaseState):
    status = WorkItemStatus.CLOSED


class WorkItemStateContext:
    """
    Context that maps a WorkItemStatus to a State implementation and executes transitions.
    Extensible: add new states by extending `_STATE_MAP`.
    """

    _STATE_MAP: dict[WorkItemStatus, type[BaseState]] = {
        WorkItemStatus.OPEN: OpenState,
        WorkItemStatus.INVESTIGATING: InvestigatingState,
        WorkItemStatus.RESOLVED: ResolvedState,
        WorkItemStatus.CLOSED: ClosedState,
    }

    def __init__(self, current_status: WorkItemStatus):
        self._current_status = current_status
        state_cls = self._STATE_MAP.get(current_status)
        if state_cls is None:
            raise ValueError(f"Unknown WorkItemStatus: {current_status}")
        self._state: BaseState = state_cls()

    @property
    def status(self) -> WorkItemStatus:
        return self._current_status

    def transition_to_investigating(self) -> WorkItemStatus:
        return self._state.move_to_investigating()

    def transition_to_resolved(self) -> WorkItemStatus:
        return self._state.move_to_resolved()

    def transition_to_closed(self) -> WorkItemStatus:
        return self._state.move_to_closed()


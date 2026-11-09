"""agentcore: a small, framework-free core for bounded tool-using agents.

Created in evidence-ledger-agent and vendored verbatim into later projects.
"""

from .adapters import (
    AdapterError,
    FixtureAdapter,
    LiveModelUnavailable,
    ModelAdapter,
    ModelResponse,
    OpenAICompatibleAdapter,
    ReplayAdapter,
)
from .loop import AgentLoop, CheckpointStore, parse_decision, render_recent
from .policy import Budget, Policy, ToolFailure, ToolRegistry, ToolSpec
from .schemas import (
    Action,
    BaseAgentState,
    Decision,
    HistoryEntry,
    PendingAction,
    StopReason,
    TokenUsage,
    ToolError,
    ToolResult,
)
from .trace import TraceWriter, read_trace, sanitize

AGENTCORE_VERSION = "0.1.0"

__all__ = [
    "AGENTCORE_VERSION",
    "Action",
    "AdapterError",
    "AgentLoop",
    "BaseAgentState",
    "Budget",
    "CheckpointStore",
    "Decision",
    "FixtureAdapter",
    "HistoryEntry",
    "LiveModelUnavailable",
    "ModelAdapter",
    "ModelResponse",
    "OpenAICompatibleAdapter",
    "PendingAction",
    "Policy",
    "ReplayAdapter",
    "StopReason",
    "TokenUsage",
    "ToolError",
    "ToolFailure",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "TraceWriter",
    "parse_decision",
    "read_trace",
    "render_recent",
    "sanitize",
]

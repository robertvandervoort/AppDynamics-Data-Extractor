"""
Canonical event type constants for the AppDynamics Events API.

Note: AppDynamics' public documentation lists many event types but is not
guaranteed to be exhaustive for every controller/version, especially for
CUSTOM events. This list is intentionally broad and grouped by category to
aid discoverability in the UI. Users can still filter by any subset.
"""

from typing import Dict, List


# Severity levels supported by the Events API retrieval endpoint
SEVERITY_LEVELS: List[str] = [
    "INFO",
    "WARN",
    "ERROR",
]


# Grouped event types for easier selection in the UI
# These are commonly observed/documented event types; the controller may emit
# a subset/superset depending on features and version.
EVENT_TYPES: Dict[str, List[str]] = {
    "Application": [
        "APPLICATION_ERROR",
        "APPLICATION_DEPLOYMENT",
        "APPLICATION_CONFIG_CHANGE",
        "CUSTOM",
    ],
    "Diagnostics": [
        "DIAGNOSTIC_SESSION",
        "ERROR_DIAGNOSTIC_SESSION",
        "SLOW_DIAGNOSTIC_SESSION",
        "DEADLOCK",
        "MEMORY_LEAK_DIAGNOSTICS",
    ],
    "Discovery": [
        "BACKEND_DISCOVERED",
        "SERVICE_ENDPOINT_DISCOVERED",
    ],
    "Agent": [
        "AGENT_EVENT",
        "AGENT_STATUS",
        "AGENT_CONFIGURATION",
    ],
    # Health rule/policy lifecycle often appears via the dedicated
    # healthrule-violations endpoint, but some controllers also surface
    # these as events.
    "Policy": [
        "POLICY_OPEN_WARNING",
        "POLICY_OPEN_CRITICAL",
        "POLICY_CLOSE_WARNING",
        "POLICY_CLOSE_CRITICAL",
    ],
}


# Convenience: a flat, de-duplicated list of all known event types
ALL_EVENT_TYPES: List[str] = sorted({t for group in EVENT_TYPES.values() for t in group})



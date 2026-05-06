"""EvoMap — observability and self-improvement signals.

Modules:
  - signals.py: Signal dataclass and SignalType/SignalDomain constants
  - observer.py: EvoMapObserver for collecting and querying signals
  - dashboard.py: DashboardAPI for dashboard views
"""

from chatgptrest.evomap.signals import Signal, SignalType, SignalDomain
from chatgptrest.evomap.observer import EvoMapObserver
from chatgptrest.evomap.dashboard import DashboardAPI

__all__ = [
    "Signal",
    "SignalType",
    "SignalDomain",
    "EvoMapObserver",
    "DashboardAPI",
]

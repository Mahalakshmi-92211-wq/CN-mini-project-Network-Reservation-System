
import json
import threading
from datetime import datetime, timezone


class SDNNotifier:
    """
    Produces structured reservation events for SDN integration.

    The initial version logs events locally. Once the Ryu controller
    API is agreed upon, this module can forward events to the controller.
    """

    def __init__(self):
        self._lock = threading.Lock()

    def notify(self, event, reservation):
        payload = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "reservation": reservation
        }

        with self._lock:
            print(
                "[SDN EVENT] "
                + json.dumps(payload, sort_keys=True)
            )

        return payload

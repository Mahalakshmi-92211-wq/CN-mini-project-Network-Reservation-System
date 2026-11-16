
import threading
import time
import itertools


class ReservationManager:
    def __init__(self, default_capacity_mbps=100):
        self.default_capacity_mbps = default_capacity_mbps

        # Capacity and reservations are tracked separately for each link.
        self.link_capacity = {}
        self.reservations = {}

        self._next_id = itertools.count(1)
        self._lock = threading.Lock()

        # Background worker that expires reservations automatically.
        self._stop_event = threading.Event()
        self._expiry_thread = threading.Thread(
            target=self._expiry_worker,
            daemon=True
        )
        self._expiry_thread.start()

    def _link_key(self, source, destination):
        # Treat a link as bidirectional for this initial model.
        return tuple(sorted((source, destination)))

    def set_link_capacity(self, source, destination, capacity_mbps):
        if not isinstance(capacity_mbps, (int, float)):
            raise ValueError("Capacity must be numeric.")

        if isinstance(capacity_mbps, bool) or capacity_mbps <= 0:
            raise ValueError("Capacity must be positive.")

        key = self._link_key(source, destination)

        with self._lock:
            self._expire_reservations_locked()

            used = sum(
                r["bandwidth_mbps"]
                for r in self.reservations.values()
                if r["link"] == key
            )

            if capacity_mbps < used:
                raise ValueError(
                    "Capacity cannot be lower than existing reservations."
                )

            self.link_capacity[key] = capacity_mbps

    def _expire_reservations_locked(self):
        now = time.monotonic()
        expired_ids = [
            reservation_id
            for reservation_id, reservation in self.reservations.items()
            if reservation["expires_at"] <= now
        ]

        for reservation_id in expired_ids:
            del self.reservations[reservation_id]
            print(f"[EXPIRED] Reservation {reservation_id} released.")

    def _expiry_worker(self):
        while not self._stop_event.wait(0.5):
            with self._lock:
                self._expire_reservations_locked()

    def reserve(self, source, destination, bandwidth_mbps,
                duration_seconds, client_id):
        # Validate request values before changing shared state.
        if not isinstance(source, str) or not source.strip():
            return {"status": "REJECTED", "message": "Invalid source."}

        if not isinstance(destination, str) or not destination.strip():
            return {"status": "REJECTED", "message": "Invalid destination."}

        if source == destination:
            return {
                "status": "REJECTED",
                "message": "Source and destination must differ."
            }

        if not isinstance(client_id, str) or not client_id.strip():
            return {"status": "REJECTED", "message": "Invalid client ID."}

        if (
            isinstance(bandwidth_mbps, bool)
            or not isinstance(bandwidth_mbps, (int, float))
            or bandwidth_mbps <= 0
        ):
            return {
                "status": "REJECTED",
                "message": "Bandwidth must be a positive number."
            }

        if (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or duration_seconds <= 0
        ):
            return {
                "status": "REJECTED",
                "message": "Duration must be a positive number."
            }

        key = self._link_key(source, destination)

        with self._lock:
            self._expire_reservations_locked()

            capacity = self.link_capacity.get(
                key, self.default_capacity_mbps
            )

            used = sum(
                r["bandwidth_mbps"]
                for r in self.reservations.values()
                if r["link"] == key
            )

            available = capacity - used

            if bandwidth_mbps > available:
                return {
                    "status": "REJECTED",
                    "message": "Insufficient bandwidth available.",
                    "capacity_mbps": capacity,
                    "used_mbps": used,
                    "available_mbps": available
                }

            reservation_id = next(self._next_id)

            reservation = {
                "reservation_id": reservation_id,
                "client_id": client_id,
                "source": source,
                "destination": destination,
                "link": key,
                "bandwidth_mbps": bandwidth_mbps,
                "duration_seconds": duration_seconds,
                "expires_at": time.monotonic() + duration_seconds
            }

            self.reservations[reservation_id] = reservation

            print(
                f"[ACCEPTED] Reservation {reservation_id}: "
                f"{bandwidth_mbps} Mbps on {source}-{destination}"
            )

            return {
                "status": "ACCEPTED",
                "reservation_id": reservation_id,
                "message": "Reservation created successfully.",
                "capacity_mbps": capacity,
                "used_mbps": used + bandwidth_mbps,
                "available_mbps": available - bandwidth_mbps
            }

    def get_status(self, source, destination):
        key = self._link_key(source, destination)

        with self._lock:
            self._expire_reservations_locked()

            capacity = self.link_capacity.get(
                key, self.default_capacity_mbps
            )

            used = sum(
                r["bandwidth_mbps"]
                for r in self.reservations.values()
                if r["link"] == key
            )

            return {
                "source": source,
                "destination": destination,
                "capacity_mbps": capacity,
                "used_mbps": used,
                "available_mbps": capacity - used
            }

    def release(self, reservation_id, client_id=None):
        with self._lock:
            self._expire_reservations_locked()

            reservation = self.reservations.get(reservation_id)

            if reservation is None:
                return {
                    "status": "NOT_FOUND",
                    "message": "Reservation does not exist or has expired."
                }

            if (
                client_id is not None
                and reservation["client_id"] != client_id
            ):
                return {
                    "status": "REJECTED",
                    "message": "Reservation belongs to another client."
                }

            del self.reservations[reservation_id]

            print(f"[RELEASED] Reservation {reservation_id}")

            return {
                "status": "RELEASED",
                "reservation_id": reservation_id,
                "message": "Bandwidth released successfully."
            }

    def close(self):
        self._stop_event.set()
        self._expiry_thread.join(timeout=2)

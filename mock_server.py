
import json
import socketserver
import threading
import time
import uuid

HOST = "127.0.0.1"
PORT = 5000
CAPACITY_MBPS = 100

reservations = []
lock = threading.Lock()

def clean_expired():
    """Remove reservations whose duration has elapsed."""
    now = time.monotonic()
    reservations[:] = [
        r for r in reservations if r["expires_at"] > now
    ]

def process_request(data):
    with lock:
        clean_expired()

        action = data.get("action", "reserve")

        # Testing-only commands. Do not assume the real server
        # will support these commands.
        if action == "reset":
            reservations.clear()
            return {"status": "ok", "message": "Mock state reset"}

        if action == "status":
            used = sum(r["bandwidth_mbps"] for r in reservations)
            return {
                "status": "ok",
                "capacity_mbps": CAPACITY_MBPS,
                "used_mbps": used,
                "available_mbps": CAPACITY_MBPS - used
            }

        client_id = data.get("client_id")
        source = data.get("source")
        destination = data.get("destination")
        bandwidth = data.get("bandwidth_mbps")
        duration = data.get("duration_seconds")

        if not all([client_id, source, destination]):
            return {
                "status": "rejected",
                "code": "INVALID_FIELDS",
                "message": "Missing client ID or endpoint"
            }

        if source == destination:
            return {
                "status": "rejected",
                "code": "INVALID_ROUTE",
                "message": "Source and destination must differ"
            }

        # Reject booleans, strings and non-numeric values.
        if isinstance(bandwidth, bool) or not isinstance(
            bandwidth, (int, float)
        ):
            return {
                "status": "rejected",
                "code": "INVALID_BANDWIDTH",
                "message": "Bandwidth must be numeric"
            }

        if not 0 < bandwidth <= CAPACITY_MBPS:
            return {
                "status": "rejected",
                "code": "INVALID_BANDWIDTH",
                "message": "Bandwidth must be between 0 and 100 Mbps"
            }

        if isinstance(duration, bool) or not isinstance(duration, int):
            return {
                "status": "rejected",
                "code": "INVALID_DURATION",
                "message": "Duration must be a whole number of seconds"
            }

        if not 1 <= duration <= 3600:
            return {
                "status": "rejected",
                "code": "INVALID_DURATION",
                "message": "Duration must be 1–3600 seconds"
            }

        used = sum(r["bandwidth_mbps"] for r in reservations)

        if used + bandwidth > CAPACITY_MBPS:
            return {
                "status": "rejected",
                "code": "INSUFFICIENT_CAPACITY",
                "message": "Not enough simulated bandwidth",
                "available_mbps": CAPACITY_MBPS - used
            }

        reservation_id = str(uuid.uuid4())

        reservations.append({
            "id": reservation_id,
            "client_id": client_id,
            "bandwidth_mbps": bandwidth,
            "expires_at": time.monotonic() + duration
        })

        return {
            "status": "accepted",
            "code": "RESERVATION_CREATED",
            "reservation_id": reservation_id,
            "bandwidth_mbps": bandwidth,
            "message": "Mock reservation accepted"
        }

class ReservationHandler(socketserver.StreamRequestHandler):
    def handle(self):
        # One JSON request per line; one response per line.
        for line in self.rfile:
            try:
                data = json.loads(line.decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Request must be a JSON object")

                result = process_request(data)

            except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
                result = {
                    "status": "rejected",
                    "code": "INVALID_JSON",
                    "message": "Send a valid JSON object"
                }

            response = json.dumps(result) + "\n"
            self.wfile.write(response.encode("utf-8"))
            self.wfile.flush()

class ThreadedTCPServer(socketserver.ThreadingMixIn,
                        socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    with ThreadedTCPServer((HOST, PORT), ReservationHandler) as server:
        print(f"Mock server listening on {HOST}:{PORT}")
        print(f"Simulated capacity: {CAPACITY_MBPS} Mbps")
        print("Press Ctrl+C to stop.")
        server.serve_forever()


import socket
import json
import threading

from reservation_manager import ReservationManager

HOST = "127.0.0.1"
PORT = 5000

manager = ReservationManager(default_capacity_mbps=100)


def handle_client(conn, addr):
    print(f"[CONNECTED] Client connected: {addr}")

    try:
        with conn:
            reader = conn.makefile("r", encoding="utf-8")

            for line in reader:
                try:
                    request = json.loads(line)

                    if not isinstance(request, dict):
                        response = {
                            "status": "REJECTED",
                            "message": "Request must be a JSON object."
                        }

                    else:
                        action = request.get("action", "reserve")

                        if action == "reserve":
                            response = manager.reserve(
                                source=request.get("source"),
                                destination=request.get("destination"),
                                bandwidth_mbps=request.get(
                                    "bandwidth_mbps"
                                ),
                                duration_seconds=request.get(
                                    "duration_seconds"
                                ),
                                client_id=request.get("client_id")
                            )

                        elif action == "status":
                            response = manager.get_status(
                                request.get("source", ""),
                                request.get("destination", "")
                            )

                        elif action == "release":
                            response = manager.release(
                                request.get("reservation_id"),
                                request.get("client_id")
                            )

                        else:
                            response = {
                                "status": "REJECTED",
                                "message": "Unknown action."
                            }

                except json.JSONDecodeError:
                    response = {
                        "status": "REJECTED",
                        "message": "Invalid JSON."
                    }

                except (TypeError, ValueError) as error:
                    response = {
                        "status": "REJECTED",
                        "message": f"Invalid request: {error}"
                    }

                message = json.dumps(response) + "\n"
                conn.sendall(message.encode("utf-8"))

    except (ConnectionError, OSError) as error:
        print(f"[ERROR] Client {addr}: {error}")

    finally:
        print(f"[DISCONNECTED] Client disconnected: {addr}")


def main():
    try:
        with socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        ) as server:
            server.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
            )
            server.bind((HOST, PORT))
            server.listen()

            print(f"[STARTED] TCP server listening on {HOST}:{PORT}")
            print("[INFO] Default link capacity: 100 Mbps")

            while True:
                conn, addr = server.accept()

                thread = threading.Thread(
                    target=handle_client,
                    args=(conn, addr),
                    daemon=True
                )
                thread.start()

    except KeyboardInterrupt:
        print("\n[STOPPED] Server shutting down.")

    finally:
        manager.close()


if __name__ == "__main__":
    main()

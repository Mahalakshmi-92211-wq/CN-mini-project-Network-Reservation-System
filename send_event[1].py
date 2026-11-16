#!/usr/bin/env python3
"""Small command-line helper to test the OS-Ken REST endpoint."""
import argparse
import json
import urllib.request
import urllib.error


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True,
                        choices=["ACCEPTED", "RELEASED", "EXPIRED"])
    parser.add_argument("--id", type=int, required=True)
    parser.add_argument("--source", default="h1")
    parser.add_argument("--destination", default="h2")
    parser.add_argument("--bandwidth", type=float, default=5)
    parser.add_argument("--url", default="http://127.0.0.1:8080/reservation")
    args = parser.parse_args()

    payload = {
        "event": args.event,
        "reservation": {
            "reservation_id": args.id,
            "source": args.source,
            "destination": args.destination,
            "bandwidth_mbps": args.bandwidth
        }
    }
    request = urllib.request.Request(
        args.url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            print(response.status, response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        print(error.code, error.read().decode("utf-8"))
        raise SystemExit(1)
    except urllib.error.URLError as error:
        print(f"Connection failed: {error.reason}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

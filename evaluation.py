
import csv
import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

HOST = "127.0.0.1"
PORT = 5000

results = []

def send_request(request):
    """Send one JSON request and measure round-trip latency."""
    start = time.perf_counter()

    try:
        with socket.create_connection((HOST, PORT), timeout=5) as sock:
            sock.settimeout(5)
            file = sock.makefile("rwb")

            file.write((json.dumps(request) + "\n").encode("utf-8"))
            file.flush()

            response = json.loads(file.readline().decode("utf-8"))

        latency_ms = (time.perf_counter() - start) * 1000
        return response, latency_ms

    except (OSError, json.JSONDecodeError, TimeoutError) as error:
        latency_ms = (time.perf_counter() - start) * 1000
        return {
            "status": "error",
            "code": "CONNECTION_ERROR",
            "message": str(error)
        }, latency_ms

def reset_mock():
    """Reset simulated reservations between independent scenarios."""
    response, _ = send_request({"action": "reset"})

    if response.get("status") != "ok":
        raise RuntimeError(f"Could not reset mock server: {response}")

def record(scenario, request, response, latency_ms):
    results.append({
        "scenario": scenario,
        "client_id": request.get("client_id", ""),
        "bandwidth_mbps": request.get("bandwidth_mbps", ""),
        "status": response.get("status", "error"),
        "response_code": response.get("code", ""),
        "latency_ms": round(latency_ms, 3)
    })

    print(
        f"{scenario:20} | "
        f"{request.get('client_id', '-'):12} | "
        f"{response.get('status', 'error'):9} | "
        f"{response.get('code', ''):24} | "
        f"{latency_ms:.2f} ms"
    )

def reserve(client_id, bandwidth, duration=60):
    return {
        "action": "reserve",
        "client_id": client_id,
        "source": "h1",
        "destination": "h2",
        "bandwidth_mbps": bandwidth,
        "duration_seconds": duration
    }

def run_one(scenario, request):
    response, latency = send_request(request)
    record(scenario, request, response, latency)
    return response

def main():
    print("\nNETWORK RESERVATION SYSTEM: EVALUATION")
    print("-" * 100)
    print(
        f"{'Scenario':20} | {'Client':12} | "
        f"{'Status':9} | {'Response code':24} | Latency"
    )
    print("-" * 100)

    # Test 1: Valid reservation
    reset_mock()
    run_one("valid_request", reserve("client_1", 20))

    # Test 2: Invalid bandwidth
    reset_mock()
    run_one("invalid_request", reserve("client_2", -10))

    # Test 3: Capacity exhaustion
    reset_mock()
    run_one("capacity_test", reserve("client_3", 80))
    run_one("capacity_test", reserve("client_4", 30))

    # Test 4: Expiration releases capacity
    reset_mock()
    run_one("expiry_test", reserve("client_5", 80, duration=2))
    print("\nWaiting 2.2 seconds for the reservation to expire...")
    time.sleep(2.2)
    run_one("expiry_test", reserve("client_6", 50))

    # Test 5: Concurrent clients
    reset_mock()
    print("\nSending 10 requests concurrently...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        for i in range(10):
            request = reserve(f"concurrent_{i+1}", 15)
            futures.append(
                executor.submit(send_request, request)
            )

        for future in as_completed(futures):
            response, latency = future.result()

            # Each concurrent request is recorded separately.
            client_id = next(
                r for r in [
                    f"concurrent_{i+1}" for i in range(10)
                ]
                if r not in {
                    row["client_id"] for row in results
                }
            ) if False else "concurrent_client"

            # Use the response-independent test record below.
            results.append({
                "scenario": "concurrent_test",
                "client_id": "",
                "bandwidth_mbps": 15,
                "status": response.get("status", "error"),
                "response_code": response.get("code", ""),
                "latency_ms": round(latency, 3)
            })

            print(
                f"{'concurrent_test':20} | "
                f"{response.get('status', 'error'):9} | "
                f"{response.get('code', ''):24} | "
                f"{latency:.2f} ms"
            )

    # Export results for the report and graph.
    with open("results.csv", "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "scenario", "client_id", "bandwidth_mbps",
            "status", "response_code", "latency_ms"
        ])
        writer.writeheader()
        writer.writerows(results)

    # Print summary statistics.
    latencies = [row["latency_ms"] for row in results]
    accepted = sum(row["status"] == "accepted" for row in results)
    rejected = sum(row["status"] == "rejected" for row in results)

    print("\n" + "=" * 45)
    print("EVALUATION SUMMARY")
    print("=" * 45)
    print(f"Total requests:     {len(results)}")
    print(f"Accepted:           {accepted}")
    print(f"Rejected:           {rejected}")
    print(f"Average latency:    {sum(latencies) / len(latencies):.2f} ms")
    print(f"Minimum latency:    {min(latencies):.2f} ms")
    print(f"Maximum latency:    {max(latencies):.2f} ms")
    print("Results saved to results.csv")

if __name__ == "__main__":
    main()

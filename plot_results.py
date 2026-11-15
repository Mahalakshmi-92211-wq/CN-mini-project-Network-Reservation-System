
import csv
from collections import defaultdict
import matplotlib.pyplot as plt

latencies = defaultdict(list)

with open("results.csv", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        latency = float(row["latency_ms"])
        latencies[row["scenario"]].append(latency)

scenarios = list(latencies.keys())
averages = [
    sum(latencies[name]) / len(latencies[name])
    for name in scenarios
]

plt.figure(figsize=(10, 5))
plt.bar(scenarios, averages)
plt.xlabel("Test scenario")
plt.ylabel("Average request latency (ms)")
plt.title("Network Reservation System: Request Latency")
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
plt.savefig("latency_graph.png", dpi=150)
plt.show()

print("Graph saved to latency_graph.png")

# Member 2 — Mininet topology and OS-Ken SDN controller

## Files
- `topology.py`: h1, h2, h3 connected to s1, OpenFlow 1.3.
- `reservation_sdn_controller.py`: OS-Ken application and REST endpoint.
- `send_event.py`: manual REST event tester.
- `tests/manual_test_plan.md`: validation checklist.

## Environment
- Python virtual environment: `~/osken-legacy-env`
- OS-Ken controller OpenFlow port: 6653
- REST API: TCP port 8080
- Hosts: h1=10.0.0.1, h2=10.0.0.2, h3=10.0.0.3

## Run
Terminal 1 (activate OS-Ken environment first):
```bash
source ~/osken-legacy-env/bin/activate
cd /path/to/member2-folder
osken-manager --ofp-tcp-listen-port 6653 reservation_sdn_controller.py
```

Terminal 2:
```bash
sudo python3 topology.py
```

In Mininet:
```text
mininet> pingall
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

Terminal 3:
```bash
python3 send_event.py --event ACCEPTED --id 1 --source h1 --destination h2 --bandwidth 5
python3 send_event.py --event RELEASED --id 1
```

## REST contract
POST `http://127.0.0.1:8080/reservation`

```json
{
  "event": "ACCEPTED",
  "reservation": {
    "reservation_id": 1,
    "source": "h1",
    "destination": "h2",
    "bandwidth_mbps": 5
  }
}
```
Events: `ACCEPTED`, `RELEASED`, `EXPIRED`.

## Implementation notes and limitations
- This version uses a basic MAC-learning PacketIn handler so ordinary host traffic can be forwarded.
- OpenFlow meters impose a maximum rate on matching IPv4 traffic; they do not guarantee minimum bandwidth or reserve shared link capacity.
- The starter implementation does not implement global admission control. Member 1's reservation manager must reject requests that exceed the configured capacity before sending ACCEPTED.
- Multiple simultaneous reservations for the same source/destination pair can create overlapping match rules. Do not claim that scenario is supported until the policy is redesigned or tested.
- The topology's host access links are individually shaped to 20 Mbps. These are not one shared 20 Mbps bottleneck.
- Verify meter support with `ovs-ofctl -O OpenFlow13 meter-features s1` and inspect `meter-stats` after installing a reservation.

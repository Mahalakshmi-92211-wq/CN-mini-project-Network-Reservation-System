import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from os_ken.base import app_manager
from os_ken.controller import ofp_event
from os_ken.controller.handler import (
    CONFIG_DISPATCHER,
    DEAD_DISPATCHER,
    MAIN_DISPATCHER,
    set_ev_cls
)
from os_ken.ofproto import ofproto_v1_3
from os_ken.lib.packet import packet, ethernet, ether_types

LOG = logging.getLogger("reservation_sdn")

HOST_IPS = {
    "h1": "10.0.0.1",
    "h2": "10.0.0.2",
    "h3": "10.0.0.3"
}


class ReservationSDNController(app_manager.OSKenApp):

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.datapaths = {}
        self.reservations = {}
        self.meter_ids = {}
        self.next_meter_id = 1
        self.mac_to_port = {}

    def start(self):
        super().start()

        controller = self

        class Handler(BaseHTTPRequestHandler):

            def do_POST(self):
                if self.path.rstrip("/") != "/reservation":
                    self.send_error(404)
                    return

                try:
                    length = int(self.headers.get("Content-Length", 0))

                    if length <= 0 or length > 1048576:
                        raise ValueError("Invalid request size")

                    payload = json.loads(
                        self.rfile.read(length).decode("utf-8")
                    )

                    result = controller.handle_event(payload)

                    body = json.dumps(result).encode()
                    self.send_response(200)

                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    body = json.dumps({
                        "status": "ERROR",
                        "message": str(exc)
                    }).encode()

                    self.send_response(400)

                except RuntimeError as exc:
                    body = json.dumps({
                        "status": "ERROR",
                        "message": str(exc)
                    }).encode()

                    self.send_response(503)

                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                LOG.info(fmt % args)

        self.rest_server = ThreadingHTTPServer(
            ("0.0.0.0", 8080),
            Handler
        )

        threading.Thread(
            target=self.rest_server.serve_forever,
            daemon=True
        ).start()

        LOG.info("REST API listening on port 8080")

    def add_flow(self, dp, match, actions, priority=10,
                 meter_id=None, cookie=0):

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        instructions = []

        if meter_id is not None:
            instructions.append(
                parser.OFPInstructionMeter(
                    meter_id,
                    ofp.OFPIT_METER
                )
            )

        instructions.append(
            parser.OFPInstructionActions(
                ofp.OFPIT_APPLY_ACTIONS,
                actions
            )
        )

        dp.send_msg(
            parser.OFPFlowMod(
                datapath=dp,
                priority=priority,
                match=match,
                instructions=instructions,
                cookie=cookie
            )
        )

    @set_ev_cls(
        ofp_event.EventOFPSwitchFeatures,
        CONFIG_DISPATCHER
    )
    def switch_features_handler(self, ev):

        dp = ev.msg.datapath
        self.datapaths[dp.id] = dp

        parser = dp.ofproto_parser
        ofp = dp.ofproto

        match = parser.OFPMatch()

        actions = [
            parser.OFPActionOutput(
                ofp.OFPP_CONTROLLER,
                ofp.OFPCML_NO_BUFFER
            )
        ]

        self.add_flow(dp, match, actions, priority=0)

        LOG.info("Switch connected: %s", dp.id)

    @set_ev_cls(
        ofp_event.EventOFPStateChange,
        [MAIN_DISPATCHER, DEAD_DISPATCHER]
    )
    def state_change_handler(self, ev):

        dp = ev.datapath

        if ev.state == MAIN_DISPATCHER:
            self.datapaths[dp.id] = dp

        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(dp.id, None)

    @set_ev_cls(
        ofp_event.EventOFPPacketIn,
        MAIN_DISPATCHER
    )
    def packet_in_handler(self, ev):

        msg = ev.msg
        dp = msg.datapath

        ofp = dp.ofproto
        parser = dp.ofproto_parser

        in_port = msg.match["in_port"]

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)

        if eth is None:
            return

        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src

        table = self.mac_to_port.setdefault(dp.id, {})
        table[src] = in_port

        out_port = table.get(dst, ofp.OFPP_FLOOD)

        actions = [
            parser.OFPActionOutput(out_port)
        ]

        if out_port != ofp.OFPP_FLOOD:

            match = parser.OFPMatch(
                in_port=in_port,
                eth_dst=dst
            )

            self.add_flow(
                dp,
                match,
                actions,
                priority=1
            )

        data = None

        if msg.buffer_id == ofp.OFP_NO_BUFFER:
            data = msg.data

        dp.send_msg(
            parser.OFPPacketOut(
                datapath=dp,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=data
            )
        )

    def install_reservation(self, reservation):

        source = reservation.get("source")
        destination = reservation.get("destination")
        bandwidth = reservation.get("bandwidth_mbps")
        reservation_id = str(reservation.get("reservation_id"))

        if source not in HOST_IPS or destination not in HOST_IPS:
            raise ValueError("Invalid source or destination")

        if source == destination:
            raise ValueError("Source and destination must differ")

        if (
            isinstance(bandwidth, bool)
            or not isinstance(bandwidth, (int, float))
            or bandwidth <= 0
        ):
            raise ValueError("Invalid bandwidth")

        if not self.datapaths:
            raise RuntimeError("No OpenFlow switch connected")

        if reservation_id in self.reservations:
            self.remove_reservation(reservation_id)

        meter_id = self.next_meter_id
        self.next_meter_id += 1

        self.meter_ids[reservation_id] = meter_id

        for dp in list(self.datapaths.values()):

            parser = dp.ofproto_parser
            ofp = dp.ofproto

            rate_kbps = max(1, int(bandwidth * 1000))

            band = parser.OFPMeterBandDrop(
                rate=rate_kbps,
                burst_size=0
            )

            dp.send_msg(
                parser.OFPMeterMod(
                    datapath=dp,
                    command=ofp.OFPMC_ADD,
                    flags=ofp.OFPMF_KBPS,
                    meter_id=meter_id,
                    bands=[band]
                )
            )

            for src_ip, dst_ip in [
                (HOST_IPS[source], HOST_IPS[destination]),
                (HOST_IPS[destination], HOST_IPS[source])
            ]:

                match = parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_src=src_ip,
                    ipv4_dst=dst_ip
                )

                actions = [
                    parser.OFPActionOutput(ofp.OFPP_FLOOD)
                ]

                self.add_flow(
                    dp,
                    match,
                    actions,
                    priority=100,
                    meter_id=meter_id,
                    cookie=meter_id
                )

        self.reservations[reservation_id] = reservation

        LOG.info(
            "Installed reservation %s: %s -> %s, %s Mbps",
            reservation_id,
            source,
            destination,
            bandwidth
        )

    def remove_reservation(self, reservation_id):

        reservation_id = str(reservation_id)

        self.reservations.pop(reservation_id, None)

        meter_id = self.meter_ids.pop(reservation_id, None)

        if meter_id is None:
            return False

        for dp in list(self.datapaths.values()):

            parser = dp.ofproto_parser
            ofp = dp.ofproto

            dp.send_msg(
                parser.OFPFlowMod(
                    datapath=dp,
                    command=ofp.OFPFC_DELETE,
                    cookie=meter_id,
                    cookie_mask=0xFFFFFFFFFFFFFFFF,
                    out_port=ofp.OFPP_ANY,
                    out_group=ofp.OFPG_ANY,
                    match=parser.OFPMatch()
                )
            )

            dp.send_msg(
                parser.OFPMeterMod(
                    datapath=dp,
                    command=ofp.OFPMC_DELETE,
                    meter_id=meter_id,
                    bands=[]
                )
            )

        return True

    def handle_event(self, payload):

        event = str(payload.get("event", "")).upper()
        reservation = payload.get("reservation")

        if not isinstance(reservation, dict):
            raise ValueError("Missing reservation object")

        reservation_id = reservation.get("reservation_id")

        if reservation_id is None:
            raise ValueError("Missing reservation_id")

        if event == "ACCEPTED":

            self.install_reservation(reservation)

            return {
                "status": "OK",
                "action": "installed",
                "reservation_id": reservation_id
            }

        elif event in ("RELEASED", "EXPIRED"):

            removed = self.remove_reservation(reservation_id)

            return {
                "status": "OK",
                "action": "removed" if removed else "not_found",
                "reservation_id": reservation_id
            }

        raise ValueError("Unknown event")

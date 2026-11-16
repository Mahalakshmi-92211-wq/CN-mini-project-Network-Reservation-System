#!/usr/bin/env python3
"""Mininet topology for the Network Resource Reservation System.

Topology: h1, h2, h3 -- s1 -- remote OS-Ken controller.
Run with: sudo python3 topology.py
"""
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def build_topology():
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        build=False
    )

    info("*** Adding remote SDN controller\n")
    net.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653
    )

    info("*** Adding OpenFlow switch and hosts\n")
    s1 = net.addSwitch("s1", protocols="OpenFlow13")
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    # Constrained links make congestion experiments possible.
    net.addLink(h1, s1, bw=20, delay="5ms")
    net.addLink(h2, s1, bw=20, delay="5ms")
    net.addLink(h3, s1, bw=20, delay="5ms")

    net.build()
    net.start()
    info("*** Network ready. Try: pingall, h1 ping -c 3 h2\n")
    info("*** Use 'exit' to stop the Mininet CLI.\n")
    CLI(net)
    net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    build_topology()

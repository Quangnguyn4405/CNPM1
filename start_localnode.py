"""
start_localnode
~~~~~~~~~~~~~~~~~

Entry point for launching a Local Web Node.
This provides the web interface on a local port, handles local P2P logic,
and proxies discovery to the Central Tracker.
"""

import argparse
from apps.localnodeapp import create_localnodeapp

PORT = 8001

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Local Node',
        description='Local Web Node for Decentralized Chat',
    )
    parser.add_argument(
        '--node-ip', type=str, default='127.0.0.1',
        help='IP address to bind the local node (default: 127.0.0.1)'
    )
    parser.add_argument(
        '--node-port', type=int, default=PORT,
        help='Port number for local web interface (default: {})'.format(PORT)
    )
    parser.add_argument(
        '--tracker-url', type=str, default='http://127.0.0.1:8000',
        help='URL of the Central Tracker (default: http://127.0.0.1:8000)'
    )

    args = parser.parse_args()
    ip = args.node_ip
    port = args.node_port
    tracker_url = args.tracker_url

    print("=" * 60)
    print("  Local Web Node")
    print("=" * 60)
    print("  Web Interface : http://{}:{}/chat.html".format(ip, port))
    print("  Tracker URL   : {}".format(tracker_url))
    print()
    print("  Open the Web Interface link in your browser to chat.")
    print("=" * 60)

    create_localnodeapp(ip, port, tracker_url=tracker_url)

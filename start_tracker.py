"""
start_tracker
~~~~~~~~~~~~~~~~~

Entry point for launching the Central Tracker Server.
Only responsible for tracking online peers and authentication.
"""

import argparse
from apps.trackerapp import create_trackerapp

PORT = 8000

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='Tracker Server',
        description='Central Tracker for Decentralized Web Node',
    )
    parser.add_argument(
        '--server-ip', type=str, default='0.0.0.0',
        help='IP address to bind the tracker (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--server-port', type=int, default=PORT,
        help='Port number to bind the tracker (default: {})'.format(PORT)
    )

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    print("=" * 60)
    print("  Tracker Server - Central Directory")
    print("=" * 60)
    print("  Listening on: http://{}:{}".format(ip, port))
    print()
    print("  API Endpoints:")
    print("    POST /login          - Authenticate (Basic Auth)")
    print("    POST /logout         - Destroy session")
    print("    POST /submit-info    - Register peer with tracker")
    print("    GET  /get-list       - Get active peer list")
    print("    POST /add-list       - Add peer to tracker")
    print("=" * 60)

    create_trackerapp(ip, port)

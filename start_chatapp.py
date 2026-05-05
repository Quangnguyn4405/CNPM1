"""
start_chatapp
~~~~~~~~~~~~~~~~~

Entry point for launching the hybrid chat application.
Combines HTTP authentication, client-server peer registration,
and peer-to-peer direct messaging via the AsynapRous framework.

Usage:
    python start_chatapp.py --server-ip 0.0.0.0 --server-port 8000
"""

import argparse
import socket
from apps.chatapp import create_chatapp

PORT = 8000

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog='ChatApp',
        description='Hybrid Chat Application (Client-Server + P2P)',
        epilog='CO3093/CO3094 Assignment 1'
    )
    parser.add_argument(
        '--server-ip', type=str, default='0.0.0.0',
        help='IP address to bind the server (default: 0.0.0.0)'
    )
    parser.add_argument(
        '--server-port', type=int, default=PORT,
        help='Port number to bind the server (default: {})'.format(PORT)
    )

    args = parser.parse_args()
    ip = args.server_ip
    port = args.server_port

    print("=" * 60)
    print("  Hybrid Chat Application - CO3093/CO3094 Assignment 1")
    print("  Student ID: 2312794")
    print("=" * 60)
    print()
    print("  Server: http://{}:{}".format(ip, port))
    print()
    print("  API Endpoints:")
    print("    POST /login          - Authenticate (Basic Auth)")
    print("    POST /logout         - Destroy session")
    print("    POST /submit-info    - Register peer with tracker")
    print("    GET  /get-list       - Get active peer list")
    print("    POST /add-list       - Add peer to tracker")
    print("    POST /connect-peer   - Connect to a peer (P2P)")
    print("    POST /broadcast-peer - Broadcast to all peers")
    print("    POST /send-peer      - Send to specific peer")
    print("    GET  /channels       - List channels")
    print("    GET  /messages       - Get channel messages")
    print("    GET  /notifications  - Get notifications")
    print("    GET  /peer-status    - Check P2P status")
    print()
    print("=" * 60)

    create_chatapp(ip, port)

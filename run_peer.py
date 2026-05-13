"""
Chạy một PeerNode độc lập, không cần HTTP server.
Dùng để demo P2P thuần túy.

Cách dùng:
  Terminal 1:  python run_peer.py --user alice --port 7001
  Terminal 2:  python run_peer.py --user bob   --port 7002

Sau đó gõ lệnh trong terminal:
  connect 127.0.0.1 7002    (alice kết nối tới bob)
  send Hello!               (gửi broadcast)
  status                    (xem peer đang kết nối)
  quit
"""

import argparse
import sys
import threading
import time
sys.path.insert(0, ".")
from daemon.peer import PeerNode


def input_loop(peer):
    print("Lệnh: connect <ip> <port> | send <message> | status | quit")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            continue

        parts = line.split(" ", 2)
        cmd = parts[0].lower()

        if cmd == "connect" and len(parts) == 3:
            ip, port = parts[1], int(parts[2])
            ok = peer.connect_to_peer(ip, port)
            print("Connected:", ok)

        elif cmd == "send" and len(parts) >= 2:
            msg = " ".join(parts[1:])
            n = peer.broadcast_message(msg)
            print("Sent to {} peer(s)".format(n))

        elif cmd == "status":
            peers = peer.get_connected_peers_info()
            if peers:
                for p in peers:
                    print("  {}:{} ({})".format(p["ip"], p["port"], p["username"]))
            else:
                print("  No connected peers")

        elif cmd == "quit":
            break

        else:
            print("Lệnh không hợp lệ")

    peer.stop()
    print("Peer stopped.")


def print_incoming(msg):
    print("\n[{}] {}: {}".format(
        msg.get("channel", "general"),
        msg.get("sender", "?"),
        msg.get("message", "")
    ))
    print("> ", end="", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="peer", help="Username")
    parser.add_argument("--port", type=int, default=7001, help="Port to listen on")
    parser.add_argument("--ip", default="127.0.0.1", help="IP to bind")
    args = parser.parse_args()

    peer = PeerNode(args.ip, args.port, args.user)
    peer.on_message = print_incoming
    peer.start()

    print("Peer '{}' listening on {}:{}".format(args.user, args.ip, args.port))

    input_loop(peer)

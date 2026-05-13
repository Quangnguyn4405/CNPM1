"""
daemon.peer
~~~~~~~~~~~~~~~~~

Peer-to-peer communication module for hybrid chat application.

Provides:
  - PeerNode: a TCP server/client node that can send/receive messages
    directly to/from other peers without routing through a central server.
  - Non-blocking message handling using threading.
  - Direct unicast and broadcast messaging.
"""

import socket
import threading
import json
import time
from .utils import get_timestamp


class PeerNode:
    """A peer node that can both listen for and initiate TCP connections.

    Each peer runs a listener thread accepting incoming connections and
    can send messages directly to other peers by their (ip, port).

    Attributes:
        ip (str): This peer's bind IP.
        port (int): This peer's listen port.
        username (str): Peer's username/display name.
        connected_peers (dict): {(ip, port): {"username": ..., "socket": ...}}
        message_log (list): All received messages.
        channels (dict): {channel_name: [messages]}
        on_message (callable): Optional callback for incoming messages.
    """

    def __init__(self, ip, port, username="anonymous"):
        self.ip = ip
        self.port = port
        self.username = username
        self.connected_peers = {}
        self.message_log = []
        self.channels = {"general": []}
        self.notifications = []
        self._lock = threading.Lock()
        self._running = False
        self._server_socket = None
        self._listener_thread = None
        self.on_message = None          # callback(message_dict)
        self.on_channel_created = None  # callback(channel_name, members)
        self.on_channel_deleted = None  # callback(channel_name)

    def start(self):
        """Start the peer listener in a background thread."""
        self._running = True
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.settimeout(1.0)
        self._server_socket.bind((self.ip, self.port))
        self._server_socket.listen(20)

        self._listener_thread = threading.Thread(
            target=self._listen_loop, daemon=True
        )
        self._listener_thread.start()
        print("[PeerNode] {} listening on {}:{}".format(
            self.username, self.ip, self.port
        ))

    def stop(self):
        """Stop the peer listener and close all connections."""
        self._running = False
        with self._lock:
            for key, info in self.connected_peers.items():
                try:
                    info.get("socket", socket.socket()).close()
                except Exception:
                    pass
            self.connected_peers.clear()
        if self._server_socket:
            self._server_socket.close()
        print("[PeerNode] {} stopped.".format(self.username))

    def _listen_loop(self):
        """Accept incoming peer connections."""
        while self._running:
            try:
                conn, addr = self._server_socket.accept()
                t = threading.Thread(
                    target=self._handle_incoming, args=(conn, addr),
                    daemon=True
                )
                t.start()
            except socket.timeout:
                continue
            except OSError:
                break

    def _handle_incoming(self, conn, addr):
        """Handle an incoming peer connection: read messages.

        Uses a persistent per-connection buffer so partial TCP frames
        (JSON split across multiple recv calls) are correctly reassembled.

        :param conn (socket): Incoming socket.
        :param addr (tuple): Peer address.
        """
        conn.settimeout(60.0)
        buf = b""
        try:
            while self._running:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                except socket.timeout:
                    continue
                except BlockingIOError:
                    continue

                # Drain all complete newline-terminated messages from the buffer
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    raw = line.decode("utf-8", errors="replace").strip()
                    if not raw:
                        continue
                    try:
                        msg = json.loads(raw)
                        self._process_message(msg, conn, addr)
                    except json.JSONDecodeError:
                        print("[PeerNode] Invalid JSON from {}: {}".format(addr, raw[:100]))

        except Exception as e:
            print("[PeerNode] Connection error from {}: {}".format(addr, e))
        finally:
            self._cleanup_peer(conn)
            conn.close()

    def _cleanup_peer(self, conn):
        """Remove a disconnected peer socket from connected_peers.

        :param conn (socket): The socket that closed.
        """
        with self._lock:
            dead = [key for key, info in self.connected_peers.items()
                    if info.get("socket") is conn]
            for key in dead:
                self.connected_peers.pop(key, None)
                print("[PeerNode] Peer {} disconnected".format(key))

    def _process_message(self, msg, conn, addr):
        """Process a received peer message.

        :param msg (dict): Parsed JSON message.
        :param conn (socket): Source connection.
        :param addr (tuple): Source address.
        """
        msg_type = msg.get("type", "chat")

        if msg_type == "handshake":
            # Register this peer
            peer_ip = msg.get("ip", addr[0])
            peer_port = msg.get("port", addr[1])
            peer_user = msg.get("username", "unknown")
            with self._lock:
                self.connected_peers[(peer_ip, peer_port)] = {
                    "username": peer_user,
                    "socket": conn,
                }
            print("[PeerNode] Handshake from {} ({}:{})".format(
                peer_user, peer_ip, peer_port
            ))
            # Send ack
            ack = json.dumps({
                "type": "handshake_ack",
                "username": self.username,
                "ip": self.ip,
                "port": self.port,
            }) + "\n"
            try:
                conn.sendall(ack.encode("utf-8"))
            except Exception:
                pass

        elif msg_type == "channel_deleted":
            channel = msg.get("channel", "")
            if channel:
                with self._lock:
                    self.channels.pop(channel, None)
                if self.on_channel_deleted:
                    self.on_channel_deleted(channel)

        elif msg_type == "channel_created":
            channel = msg.get("channel", "")
            members = msg.get("members")  # None = public, list = private
            sender = msg.get("sender", "unknown")
            if channel:
                # Only join if public or this peer is an invited member
                if members is None or self.username in members:
                    with self._lock:
                        if channel not in self.channels:
                            self.channels[channel] = []
                    if self.on_channel_created:
                        self.on_channel_created(channel, members, sender)

        elif msg_type == "chat":
            # Skip own messages echoed back via P2P
            if msg.get("sender_ip") == self.ip and msg.get("sender_port") == self.port:
                return
            channel = msg.get("channel", "general")
            with self._lock:
                if channel not in self.channels:
                    self.channels[channel] = []
                self.channels[channel].append(msg)
                self.message_log.append(msg)
                self.notifications.append({
                    "from": msg.get("sender", "unknown"),
                    "channel": channel,
                    "preview": msg.get("message", "")[:50],
                    "timestamp": msg.get("timestamp", get_timestamp()),
                })
            if self.on_message:
                self.on_message(msg)

        elif msg_type == "handshake_ack":
            peer_ip = msg.get("ip", addr[0])
            peer_port = msg.get("port", addr[1])
            peer_user = msg.get("username", "unknown")
            with self._lock:
                self.connected_peers[(peer_ip, peer_port)] = {
                    "username": peer_user,
                    "socket": conn,
                }

    def connect_to_peer(self, peer_ip, peer_port):
        """Initiate a TCP connection to another peer and handshake.

        :param peer_ip (str): Target peer IP.
        :param peer_port (int): Target peer port.
        :rtype: bool - True if connected.
        """
        # Refuse self-connection
        if peer_port == self.port and peer_ip in (self.ip, "127.0.0.1", "0.0.0.0", "localhost"):
            print("[PeerNode] Refused self-connection to {}:{}".format(peer_ip, peer_port))
            return False
        # Refuse duplicate connection
        with self._lock:
            if (peer_ip, peer_port) in self.connected_peers:
                print("[PeerNode] Already connected to {}:{}".format(peer_ip, peer_port))
                return True
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5.0)
            sock.connect((peer_ip, peer_port))

            # Send handshake
            handshake = json.dumps({
                "type": "handshake",
                "username": self.username,
                "ip": self.ip,
                "port": self.port,
            }) + "\n"
            sock.sendall(handshake.encode("utf-8"))

            # Wait for ack — buffer until newline so partial frames are handled
            ack_buf = b""
            while b"\n" not in ack_buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                ack_buf += chunk
            data = ack_buf.decode("utf-8", errors="replace").strip()
            if data:
                try:
                    ack = json.loads(data)
                except json.JSONDecodeError:
                    sock.close()
                    return False

                peer_user = ack.get("username", "unknown")
                with self._lock:
                    self.connected_peers[(peer_ip, peer_port)] = {
                        "username": peer_user,
                        "socket": sock,
                    }
                print("[PeerNode] Connected to {} ({}:{})".format(
                    peer_user, peer_ip, peer_port
                ))

                # Start reading from this peer in background
                t = threading.Thread(
                    target=self._handle_incoming,
                    args=(sock, (peer_ip, peer_port)),
                    daemon=True
                )
                t.start()
                return True

            sock.close()
            return False
        except Exception as e:
            print("[PeerNode] Failed to connect to {}:{} - {}".format(
                peer_ip, peer_port, e
            ))
            sock.close()
            return False

    def send_message(self, peer_ip, peer_port, message, channel="general", sender=None):
        """Send a direct message to a specific peer.

        :param peer_ip (str): Target peer IP.
        :param peer_port (int): Target peer port.
        :param message (str): Message text.
        :param channel (str): Channel name.
        :param sender (str): Override sender name (uses self.username if None).
        :rtype: bool
        """
        msg_dict = {
            "type": "chat",
            "sender": sender or self.username,
            "sender_ip": self.ip,
            "sender_port": self.port,
            "channel": channel,
            "message": message,
            "timestamp": get_timestamp(),
        }
        # Also log locally
        with self._lock:
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(msg_dict)
            self.message_log.append(msg_dict)

        return self._send_to_peer(peer_ip, peer_port, msg_dict)

    def broadcast_message(self, message, channel="general", sender=None):
        """Broadcast a message to all connected peers.

        :param message (str): Message text.
        :param channel (str): Channel name.
        :param sender (str): Override sender name (uses self.username if None).
        :rtype: int - number of peers successfully sent to.
        """
        msg_dict = {
            "type": "chat",
            "sender": sender or self.username,
            "sender_ip": self.ip,
            "sender_port": self.port,
            "channel": channel,
            "message": message,
            "timestamp": get_timestamp(),
        }
        # Log locally
        with self._lock:
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(msg_dict)
            self.message_log.append(msg_dict)

        success_count = 0
        with self._lock:
            peers = list(self.connected_peers.keys())

        for (pip, pport) in peers:
            if self._send_to_peer(pip, pport, msg_dict):
                success_count += 1
        return success_count

    def _send_to_peer(self, peer_ip, peer_port, msg_dict):
        """Send a JSON message to a specific peer socket.

        :param peer_ip (str): Peer IP.
        :param peer_port (int): Peer port.
        :param msg_dict (dict): Message payload.
        :rtype: bool
        """
        with self._lock:
            peer_info = self.connected_peers.get((peer_ip, peer_port))

        if not peer_info or "socket" not in peer_info:
            # Try to establish new connection
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5.0)
                sock.connect((peer_ip, peer_port))
                with self._lock:
                    if (peer_ip, peer_port) in self.connected_peers:
                        self.connected_peers[(peer_ip, peer_port)]["socket"] = sock
                    else:
                        self.connected_peers[(peer_ip, peer_port)] = {"socket": sock}
                peer_info = {"socket": sock}
            except Exception as e:
                print("[PeerNode] Cannot reach {}:{}: {}".format(peer_ip, peer_port, e))
                return False

        try:
            raw = json.dumps(msg_dict) + "\n"
            peer_info["socket"].sendall(raw.encode("utf-8"))
            return True
        except Exception as e:
            print("[PeerNode] Send failed to {}:{}: {}".format(peer_ip, peer_port, e))
            # Close the dead socket and remove peer entry
            try:
                peer_info["socket"].close()
            except Exception:
                pass
            with self._lock:
                self.connected_peers.pop((peer_ip, peer_port), None)
            return False

    def broadcast_channel_created(self, channel_name, sender=None, members=None):
        """Notify all connected peers that a new channel was created.

        :param channel_name (str): Name of the new channel.
        :param sender (str): Username of the creator.
        :param members (set|None): Invited usernames, or None for public.
        """
        msg = {
            "type": "channel_created",
            "channel": channel_name,
            "members": list(members) if members is not None else None,
            "sender": sender or self.username,
            "sender_ip": self.ip,
            "sender_port": self.port,
            "timestamp": get_timestamp(),
        }
        with self._lock:
            peers = list(self.connected_peers.keys())
        for (pip, pport) in peers:
            self._send_to_peer(pip, pport, msg)

    def broadcast_channel_deleted(self, channel_name, sender=None):
        """Notify all connected peers that a channel was deleted.

        :param channel_name (str): Name of the deleted channel.
        :param sender (str): Username of the deleter.
        """
        msg = {
            "type": "channel_deleted",
            "channel": channel_name,
            "sender": sender or self.username,
            "sender_ip": self.ip,
            "sender_port": self.port,
            "timestamp": get_timestamp(),
        }
        with self._lock:
            peers = list(self.connected_peers.keys())
        for (pip, pport) in peers:
            self._send_to_peer(pip, pport, msg)

    def delete_channel(self, channel_name):
        """Remove a channel from this peer's local state.

        :param channel_name (str): Channel to remove.
        :rtype: bool - True if removed, False if not found.
        """
        with self._lock:
            if channel_name in self.channels:
                del self.channels[channel_name]
                return True
            return False

    def get_channels(self):
        """Get list of channel names.

        :rtype: list
        """
        with self._lock:
            return list(self.channels.keys())

    def create_channel(self, channel_name):
        """Create a new channel if it doesn't exist.

        :param channel_name (str): Name of the channel.
        :rtype: bool - True if created, False if already exists.
        """
        with self._lock:
            if channel_name in self.channels:
                return False
            self.channels[channel_name] = []
            return True

    def join_channel(self, channel_name):
        """Join an existing channel (create if not exists).

        :param channel_name (str): Name of the channel.
        """
        with self._lock:
            if channel_name not in self.channels:
                self.channels[channel_name] = []

    def get_messages(self, channel="general", limit=50):
        """Get messages from a channel.

        :param channel (str): Channel name.
        :param limit (int): Max messages to return.
        :rtype: list of dict
        """
        with self._lock:
            msgs = self.channels.get(channel, [])
            return msgs[-limit:]

    def get_notifications(self, clear=True):
        """Get pending notifications.

        :param clear (bool): Clear notifications after fetching.
        :rtype: list of dict
        """
        with self._lock:
            notifs = list(self.notifications)
            if clear:
                self.notifications.clear()
            return notifs

    def get_connected_peers_info(self):
        """Get info about connected peers.

        :rtype: list of dict
        """
        with self._lock:
            result = []
            for (pip, pport), info in self.connected_peers.items():
                result.append({
                    "ip": pip,
                    "port": pport,
                    "username": info.get("username", "unknown"),
                })
            return result
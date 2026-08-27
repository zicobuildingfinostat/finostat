"""A small RFC 6455 WebSocket client built on sockets and ssl.

The standard library ships a WebSocket *server* helper but no client, and this
project deliberately avoids third-party packages, so the client lives here.

Only what a market data feed needs: connect, send text, receive binary and text,
answer pings, close cleanly. No extensions, no compression.
"""
from __future__ import annotations

import base64
import errno
import hashlib
import os
import socket
import ssl
import struct
from urllib.parse import urlparse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

MAX_FRAME = 8 * 1024 * 1024  # refuse absurd frames rather than allocating blindly


class WebSocketError(Exception):
    pass


class WebSocketClosed(WebSocketError):
    pass


class WebSocketRedirect(WebSocketError):
    """The handshake was answered with a redirect to another endpoint."""

    def __init__(self, location: str):
        super().__init__(f"redirected to {location}")
        self.location = location


class WebSocket:
    """A blocking client connection. One reader thread is the intended usage."""

    def __init__(self, url: str, headers: dict | None = None, timeout: float = 30.0):
        self.url = url
        self._timeout = timeout
        parts = urlparse(url)
        if parts.scheme not in ("ws", "wss"):
            raise WebSocketError(f"not a websocket url: {url}")
        secure = parts.scheme == "wss"
        host = parts.hostname
        if not host:
            raise WebSocketError(f"no host in url: {url}")
        port = parts.port or (443 if secure else 80)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        raw = socket.create_connection((host, port), timeout=timeout)
        raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        if secure:
            ctx = ssl.create_default_context()
            raw = ctx.wrap_socket(raw, server_hostname=host)
        self.sock = raw
        self._buf = b""
        self._closed = False
        try:
            self._handshake(host, port, path, secure, headers or {})
        except Exception:
            self.close(send_close=False)
            raise

    # -- handshake ----------------------------------------------------------
    def _handshake(self, host, port, path, secure, headers):
        key = base64.b64encode(os.urandom(16)).decode()
        origin_port = "" if (secure and port == 443) or (not secure and port == 80) else f":{port}"
        lines = [
            f"GET {path} HTTP/1.1",
            f"Host: {host}{origin_port}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {key}",
            "Sec-WebSocket-Version: 13",
        ]
        for name, value in headers.items():
            lines.append(f"{name}: {value}")
        self.sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())

        head = self._read_until(b"\r\n\r\n", limit=64 * 1024)
        status_line, _, rest = head.partition(b"\r\n")
        try:
            code = int(status_line.split()[1])
        except (IndexError, ValueError):
            raise WebSocketError(f"malformed response: {status_line[:120]!r}")
        if code in (301, 302, 303, 307, 308):
            for line in rest.split(b"\r\n"):
                name, _, value = line.partition(b":")
                if name.strip().lower() == b"location":
                    raise WebSocketRedirect(value.strip().decode())
            raise WebSocketError(f"HTTP {code} with no Location header")
        if code != 101:
            # Read the response body too -- Kite explains a bad token in there,
            # and the headers alone are useless for diagnosis.
            length = 0
            for line in rest.split(b"\r\n"):
                name, _, value = line.partition(b":")
                if name.strip().lower() == b"content-length":
                    try:
                        length = int(value.strip())
                    except ValueError:
                        length = 0
            body = b""
            if length:
                try:
                    self.sock.settimeout(5.0)
                    body = self._recv_exact(min(length, 8192))
                except (WebSocketError, OSError):
                    body = self._buf
            text = body.decode("utf-8", "replace").strip()[:300]
            raise WebSocketError(f"handshake rejected: HTTP {code} {text}".strip())

        accept = None
        for line in rest.split(b"\r\n"):
            name, _, value = line.partition(b":")
            if name.strip().lower() == b"sec-websocket-accept":
                accept = value.strip().decode()
        expected = base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()
        if accept != expected:
            raise WebSocketError("bad Sec-WebSocket-Accept -- not a websocket peer")

    def _read_until(self, marker: bytes, limit: int) -> bytes:
        while marker not in self._buf:
            if len(self._buf) > limit:
                raise WebSocketError("response headers too large")
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketClosed("closed during handshake")
            self._buf += chunk
        head, _, tail = self._buf.partition(marker)
        self._buf = tail
        return head + marker

    # -- framing ------------------------------------------------------------
    def _recv_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            try:
                chunk = self.sock.recv(max(4096, n - len(self._buf)))
            except socket.timeout:
                raise
            except OSError as exc:
                if exc.errno == errno.EINTR:
                    continue
                raise WebSocketClosed(str(exc)) from exc
            if not chunk:
                raise WebSocketClosed("peer closed the connection")
            self._buf += chunk
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def _read_frame(self) -> tuple[int, bytes, bool]:
        b0, b1 = self._recv_exact(2)
        fin = bool(b0 & 0x80)
        opcode = b0 & 0x0F
        masked = bool(b1 & 0x80)
        length = b1 & 0x7F
        if length == 126:
            (length,) = struct.unpack(">H", self._recv_exact(2))
        elif length == 127:
            (length,) = struct.unpack(">Q", self._recv_exact(8))
        if length > MAX_FRAME:
            raise WebSocketError(f"frame too large: {length}")
        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked and payload:
            payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        return opcode, payload, fin

    def _send_frame(self, opcode: int, payload: bytes = b"") -> None:
        if self._closed:
            raise WebSocketClosed("socket already closed")
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < (1 << 16):
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        # A client MUST mask every frame it sends (RFC 6455 §5.3).
        mask = os.urandom(4)
        header += mask
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(bytes(header) + masked)

    # -- public api ---------------------------------------------------------
    def send_text(self, text: str) -> None:
        self._send_frame(OP_TEXT, text.encode("utf-8"))

    def send_binary(self, payload: bytes) -> None:
        """Some servers (Upstox) require the subscribe JSON in a binary frame."""
        self._send_frame(OP_BINARY, payload)

    def recv(self) -> tuple[str, bytes]:
        """Block for the next application message.

        Returns ("text"|"binary", payload). Pings are answered and control
        frames handled here, so callers only ever see real messages.
        """
        buffer = b""
        kind = None
        while True:
            opcode, payload, fin = self._read_frame()
            if opcode == OP_PING:
                self._send_frame(OP_PONG, payload)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CLOSE:
                self._closed = True
                code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005
                reason = payload[2:].decode("utf-8", "replace")
                raise WebSocketClosed(f"peer closed ({code}) {reason}".strip())
            if opcode in (OP_TEXT, OP_BINARY):
                if kind is not None:
                    raise WebSocketError("interleaved message frames")
                kind = "text" if opcode == OP_TEXT else "binary"
                buffer = payload
            elif opcode == OP_CONT:
                if kind is None:
                    raise WebSocketError("continuation without a start frame")
                buffer += payload
            else:
                raise WebSocketError(f"unexpected opcode {opcode:#x}")
            if fin:
                return kind, buffer

    def settimeout(self, seconds: float | None) -> None:
        self.sock.settimeout(seconds)

    def close(self, send_close: bool = True) -> None:
        if send_close and not self._closed:
            try:
                self._send_frame(OP_CLOSE, struct.pack(">H", 1000))
            except (OSError, WebSocketError):
                pass
        self._closed = True
        try:
            self.sock.close()
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def connect(url: str, headers: dict | None = None, timeout: float = 30.0,
            max_redirects: int = 3) -> WebSocket:
    """Open a connection, following handshake redirects.

    Upstox answers the documented feed URL with a redirect to a signed,
    short-lived endpoint, so following them is required rather than optional.
    """
    seen = []
    for _ in range(max_redirects + 1):
        try:
            return WebSocket(url, headers=headers, timeout=timeout)
        except WebSocketRedirect as hop:
            location = hop.location
            if location in seen:
                raise WebSocketError(f"redirect loop via {location}")
            seen.append(location)
            if location.startswith("http://"):
                location = "ws://" + location[len("http://"):]
            elif location.startswith("https://"):
                location = "wss://" + location[len("https://"):]
            url = location
    raise WebSocketError(f"too many redirects (last: {url})")

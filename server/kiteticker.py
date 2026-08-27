"""Kite Connect streaming protocol: binary tick decoding.

Pure protocol, no I/O and no project imports, so it can be tested against
synthetic packets without a broker connection.

A binary message is an envelope of one or more packets:

    [uint16 packet_count]  then, repeated:  [uint16 length][length bytes]

Packet layout is inferred from its length. The trap worth knowing: index
packets order OHLC as **high, low, open, close**, while tradable instruments
use **open, high, low, close**. Reading an index packet with the tradable
layout silently swaps open and high.
"""
from __future__ import annotations

import struct

# instrument_token & 0xFF identifies the exchange segment
SEG_NSE, SEG_NFO, SEG_CDS, SEG_BSE, SEG_BFO, SEG_BCD, SEG_MCX, SEG_MCXSX, SEG_INDICES = range(1, 10)

LTP = "ltp"
QUOTE = "quote"
FULL = "full"


def segment_of(token: int) -> int:
    return token & 0xFF


def divisor_for(token: int) -> float:
    """Prices arrive as scaled integers; the scale depends on the segment."""
    segment = segment_of(token)
    if segment == SEG_CDS:
        return 10_000_000.0
    if segment == SEG_BCD:
        return 10_000.0
    return 100.0


def is_index(token: int) -> bool:
    return segment_of(token) == SEG_INDICES


def split_packets(data: bytes) -> list[bytes]:
    """Peel an envelope into its packets. A heartbeat is 1 byte and yields none."""
    if len(data) < 2:
        return []
    (count,) = struct.unpack_from(">H", data, 0)
    packets, offset = [], 2
    for _ in range(count):
        if offset + 2 > len(data):
            break
        (length,) = struct.unpack_from(">H", data, offset)
        offset += 2
        if offset + length > len(data):
            break  # truncated envelope: keep what parsed cleanly
        packets.append(data[offset:offset + length])
        offset += length
    return packets


def _i32(buf: bytes, at: int) -> int:
    return struct.unpack_from(">i", buf, at)[0]


def parse_packet(packet: bytes) -> dict | None:
    """Decode one packet. Returns None for a length this protocol does not define."""
    size = len(packet)
    if size < 8:
        return None
    token = struct.unpack_from(">I", packet, 0)[0]
    div = divisor_for(token)
    tick: dict = {"instrument_token": token, "tradable": not is_index(token)}

    if size == 8:
        tick["mode"] = LTP
        tick["last_price"] = _i32(packet, 4) / div
        return tick

    if size in (28, 32):
        # Index packet. Note the OHLC order: high, low, open, close.
        tick["mode"] = QUOTE if size == 28 else FULL
        tick["last_price"] = _i32(packet, 4) / div
        tick["ohlc"] = {
            "high": _i32(packet, 8) / div,
            "low": _i32(packet, 12) / div,
            "open": _i32(packet, 16) / div,
            "close": _i32(packet, 20) / div,
        }
        if size == 32:
            tick["exchange_timestamp"] = _i32(packet, 28)
        close = tick["ohlc"]["close"]
        tick["change"] = ((tick["last_price"] - close) * 100.0 / close) if close else 0.0
        return tick

    if size in (44, 184):
        tick["mode"] = QUOTE if size == 44 else FULL
        tick["last_price"] = _i32(packet, 4) / div
        tick["last_traded_quantity"] = _i32(packet, 8)
        tick["average_traded_price"] = _i32(packet, 12) / div
        tick["volume_traded"] = _i32(packet, 16)
        tick["total_buy_quantity"] = _i32(packet, 20)
        tick["total_sell_quantity"] = _i32(packet, 24)
        tick["ohlc"] = {
            "open": _i32(packet, 28) / div,
            "high": _i32(packet, 32) / div,
            "low": _i32(packet, 36) / div,
            "close": _i32(packet, 40) / div,
        }
        close = tick["ohlc"]["close"]
        tick["change"] = ((tick["last_price"] - close) * 100.0 / close) if close else 0.0
        if size == 184:
            tick["last_trade_time"] = _i32(packet, 44)
            tick["oi"] = _i32(packet, 48)
            tick["oi_day_high"] = _i32(packet, 52)
            tick["oi_day_low"] = _i32(packet, 56)
            tick["exchange_timestamp"] = _i32(packet, 60)
            depth: dict[str, list] = {"buy": [], "sell": []}
            at = 64
            for side in ("buy", "sell"):
                for _ in range(5):
                    depth[side].append({
                        "quantity": _i32(packet, at),
                        "price": _i32(packet, at + 4) / div,
                        "orders": struct.unpack_from(">H", packet, at + 8)[0],
                    })
                    at += 12
            tick["depth"] = depth
        return tick

    return None


def parse_binary(data: bytes) -> list[dict]:
    """Decode a whole binary message into ticks, skipping anything unrecognised."""
    out = []
    for packet in split_packets(data):
        tick = parse_packet(packet)
        if tick is not None:
            out.append(tick)
    return out


# -- outbound messages ------------------------------------------------------

def subscribe_message(tokens) -> str:
    import json
    return json.dumps({"a": "subscribe", "v": list(tokens)})


def unsubscribe_message(tokens) -> str:
    import json
    return json.dumps({"a": "unsubscribe", "v": list(tokens)})


def mode_message(mode: str, tokens) -> str:
    import json
    return json.dumps({"a": "mode", "v": [mode, list(tokens)]})

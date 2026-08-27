"""A minimal protobuf wire-format reader.

Upstox streams protobuf, and this project takes no third-party dependencies, so
the ~40 lines of wire format that actually matter live here.

Only decoding is implemented, and only the four wire types protobuf 3 emits.
Field numbers are not interpreted -- the caller maps them to names using the
.proto schema, which keeps this file schema-agnostic and testable on its own.
"""
from __future__ import annotations

import struct

VARINT, FIXED64, LENGTH, FIXED32 = 0, 1, 2, 5


class ProtoError(ValueError):
    pass


def read_varint(buf: bytes, at: int) -> tuple[int, int]:
    """Return (value, next_offset)."""
    result = shift = 0
    while True:
        if at >= len(buf):
            raise ProtoError("truncated varint")
        byte = buf[at]
        at += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, at
        shift += 7
        if shift > 63:
            raise ProtoError("varint too long")


def decode(buf: bytes) -> dict[int, list]:
    """Decode one message into {field_number: [raw values]}.

    Raw values are int for varint/fixed32, float for fixed64 (protobuf doubles
    are the only fixed64 this schema uses), and bytes for length-delimited.
    Repeated fields therefore fall out naturally as multi-element lists.
    """
    out: dict[int, list] = {}
    at = 0
    while at < len(buf):
        key, at = read_varint(buf, at)
        field, wire = key >> 3, key & 7
        if wire == VARINT:
            value, at = read_varint(buf, at)
        elif wire == FIXED64:
            if at + 8 > len(buf):
                raise ProtoError("truncated fixed64")
            (value,) = struct.unpack_from("<d", buf, at)
            at += 8
        elif wire == LENGTH:
            length, at = read_varint(buf, at)
            if at + length > len(buf):
                raise ProtoError("truncated length-delimited field")
            value = buf[at:at + length]
            at += length
        elif wire == FIXED32:
            if at + 4 > len(buf):
                raise ProtoError("truncated fixed32")
            (value,) = struct.unpack_from("<I", buf, at)
            at += 4
        else:
            raise ProtoError(f"unsupported wire type {wire}")
        out.setdefault(field, []).append(value)
    return out


# -- typed accessors --------------------------------------------------------

def first(msg: dict, field: int):
    values = msg.get(field)
    return values[0] if values else None


def as_double(msg: dict, field: int, default: float | None = None):
    value = first(msg, field)
    return float(value) if isinstance(value, float) else default


def as_int(msg: dict, field: int, default: int | None = None):
    value = first(msg, field)
    return int(value) if isinstance(value, int) else default


def as_str(msg: dict, field: int, default: str = "") -> str:
    value = first(msg, field)
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else default


def as_message(msg: dict, field: int) -> dict | None:
    value = first(msg, field)
    return decode(value) if isinstance(value, bytes) else None


def as_messages(msg: dict, field: int) -> list[dict]:
    return [decode(v) for v in msg.get(field, []) if isinstance(v, bytes)]


def as_map(msg: dict, field: int) -> dict[str, dict]:
    """Decode a protobuf map<string, Message> field.

    Map entries are ordinary messages on the wire: field 1 is the key, field 2
    the value. Nothing about a map is special once you know that.
    """
    out: dict[str, dict] = {}
    for entry in as_messages(msg, field):
        key = as_str(entry, 1)
        value = first(entry, 2)
        if key and isinstance(value, bytes):
            out[key] = decode(value)
    return out

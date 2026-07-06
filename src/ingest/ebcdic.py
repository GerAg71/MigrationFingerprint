"""EBCDIC and mainframe-numeric codecs (MS-2.2; spec §10.1–10.2, REQ-023).

Decoders for the LayoutSpec field types:
  packed  — COMP-3 packed decimal: two BCD digits per byte, sign in the
            final low nibble (C/F positive, D negative; anything else is a
            field-level fault, FM-006).
  zoned   — zoned decimal with sign overpunch on the last position. EBCDIC:
            digits 0xF?, final high nibble C/F (+) or D (−). ASCII: trailing
            overpunch characters {A–I (+0..+9) and }J–R (−0..−9).
  binary  — big-endian two's-complement integer.
All numeric decodes apply the implied decimal position exactly, in Decimal
(REQ-017): digits × 10^-decimals.

Encoders are the mirror images, used by the synthetic-data generator and the
golden fixtures so decode tests round-trip through one implementation.
"""

from __future__ import annotations

from decimal import Decimal

EBCDIC_CODEPAGES = {"cp037", "cp1140"}
EBCDIC_SPACE = 0x40

_ASCII_POSITIVE_OVERPUNCH = {"{": 0, **{chr(ord("A") + d - 1): d for d in range(1, 10)}}
_ASCII_NEGATIVE_OVERPUNCH = {"}": 0, **{chr(ord("J") + d - 1): d for d in range(1, 10)}}


class FieldDecodeError(ValueError):
    """A field-level decode fault (invalid digit or sign nibble). Per spec
    §10.5 this annotates the field and ingestion continues — it is evidence
    for FM-005/FM-006, not a reason to drop the record."""


def _scaled(digits: int, decimals: int, negative: bool) -> Decimal:
    value = Decimal(digits).scaleb(-decimals)
    return -value if negative else value


def decode_packed(raw: bytes, decimals: int = 0) -> Decimal:
    """COMP-3: 2N-1 digits in N bytes, sign in the final low nibble."""
    if not raw:
        raise FieldDecodeError("packed field is empty")
    digits = 0
    for byte in raw[:-1]:
        high, low = byte >> 4, byte & 0x0F
        if high > 9 or low > 9:
            raise FieldDecodeError(f"invalid packed digit nibble in byte 0x{byte:02X}")
    for byte in raw[:-1]:
        digits = digits * 100 + (byte >> 4) * 10 + (byte & 0x0F)
    last = raw[-1]
    last_digit, sign = last >> 4, last & 0x0F
    if last_digit > 9:
        raise FieldDecodeError(f"invalid packed digit nibble in byte 0x{last:02X}")
    if sign in (0x0C, 0x0F):
        negative = False
    elif sign == 0x0D:
        negative = True
    else:
        raise FieldDecodeError(f"invalid packed sign nibble 0x{sign:X}")
    return _scaled(digits * 10 + last_digit, decimals, negative)


def encode_packed(value: Decimal, length: int, decimals: int,
                  sign_nibble: int | None = None) -> bytes:
    """Inverse of decode_packed. sign_nibble overrides the sign (used by
    fixtures to fabricate FM-006 sign faults)."""
    negative = value < 0
    digits = str(abs(value).scaleb(decimals).to_integral_value())
    capacity = length * 2 - 1
    if len(digits) > capacity:
        raise ValueError(f"{value} does not fit packed({length},{decimals})")
    digits = digits.rjust(capacity, "0")
    if sign_nibble is None:
        sign_nibble = 0x0D if negative else 0x0C
    out = bytearray()
    for i in range(0, capacity - 1, 2):
        out.append(int(digits[i]) << 4 | int(digits[i + 1]))
    out.append(int(digits[-1]) << 4 | sign_nibble)
    return bytes(out)


def decode_zoned(raw: bytes, decimals: int = 0, ebcdic: bool = True) -> Decimal:
    """Zoned decimal with sign overpunch on the final position."""
    if not raw:
        raise FieldDecodeError("zoned field is empty")
    if ebcdic:
        digits = 0
        for byte in raw[:-1]:
            if byte >> 4 != 0x0F or byte & 0x0F > 9:
                raise FieldDecodeError(f"invalid zoned byte 0x{byte:02X}")
            digits = digits * 10 + (byte & 0x0F)
        last = raw[-1]
        zone, last_digit = last >> 4, last & 0x0F
        if last_digit > 9:
            raise FieldDecodeError(f"invalid zoned byte 0x{last:02X}")
        if zone in (0x0C, 0x0F):
            negative = False
        elif zone == 0x0D:
            negative = True
        else:
            raise FieldDecodeError(f"invalid zoned sign zone 0x{zone:X}")
        return _scaled(digits * 10 + last_digit, decimals, negative)

    text = raw.decode("ascii")
    body, last = text[:-1], text[-1]
    if not body.isdigit() and body != "":
        raise FieldDecodeError(f"invalid zoned digits {body!r}")
    if last.isdigit():
        negative, last_digit = False, int(last)
    elif last in _ASCII_POSITIVE_OVERPUNCH:
        negative, last_digit = False, _ASCII_POSITIVE_OVERPUNCH[last]
    elif last in _ASCII_NEGATIVE_OVERPUNCH:
        negative, last_digit = True, _ASCII_NEGATIVE_OVERPUNCH[last]
    else:
        raise FieldDecodeError(f"invalid zoned overpunch {last!r}")
    digits = int(body or "0") * 10 + last_digit
    return _scaled(digits, decimals, negative)


def encode_zoned(value: Decimal, length: int, decimals: int,
                 ebcdic: bool = True) -> bytes:
    negative = value < 0
    digits = str(abs(value).scaleb(decimals).to_integral_value())
    if len(digits) > length:
        raise ValueError(f"{value} does not fit zoned({length},{decimals})")
    digits = digits.rjust(length, "0")
    if ebcdic:
        out = bytearray(0xF0 | int(d) for d in digits[:-1])
        zone = 0x0D if negative else 0x0C
        out.append(zone << 4 | int(digits[-1]))
        return bytes(out)
    last_digit = int(digits[-1])
    table = _ASCII_NEGATIVE_OVERPUNCH if negative else _ASCII_POSITIVE_OVERPUNCH
    overpunch = next(ch for ch, d in table.items() if d == last_digit)
    return (digits[:-1] + overpunch).encode("ascii")


def decode_binary(raw: bytes, decimals: int = 0) -> Decimal:
    if not raw:
        raise FieldDecodeError("binary field is empty")
    return _scaled(int.from_bytes(raw, "big", signed=True), decimals, False)


def encode_binary(value: Decimal, length: int, decimals: int = 0) -> bytes:
    integral = int(value.scaleb(decimals).to_integral_value())
    return integral.to_bytes(length, "big", signed=True)

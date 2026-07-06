# Appendix D.4 fixture — EBCDIC loans fragment

`omni-loans-v1.json` is the spec §10.2 LayoutSpec verbatim; `loans.dat`
holds two 220-byte cp037 records (block framing, no separators).

Hex annotations (golden decode values asserted in tests):

- Record 1 `outstanding_balance` (packed, bytes 25–30): `00001043217C`
  -> 0104321 7C -> +1043217 with 2 implied decimals -> **10432.17**
- Record 2 `outstanding_balance`: `00000025075D`
  -> sign nibble D -> **-250.75**
- Record 1 `rate` (zoned, bytes 39–43): `F0F0F5F2C5`
  -> F0 F0 F5 F2 C5 (C-zone overpunch +5) -> 00525 with 4 implied
  decimals -> **0.0525**
- Record 2 `origination_date`: `00000000` with zero_is_null -> **null**
  (never 0001-01-01)

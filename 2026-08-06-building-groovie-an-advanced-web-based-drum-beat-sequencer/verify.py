#!/usr/bin/env python3
"""A port of the encoding cost model in groovie's model.js.

The figures in this post put exact bit counts on the page, and a figure that
disagrees with the encoder is worse than no figure at all. This is the part of
model.js those counts come from, close enough to the original to be checked
against it by eye: encode_row_cells and the helpers it leans on, plus the bit
length of a write_var value.

Run it on its own to print what each row of the figures costs and how the
timeline lane in the figure is written. gen_svgs.py imports it so that the
numbers drawn are the numbers computed here rather than a second copy.

Kept next to the post so the figures can be regenerated if the encoding
changes. Update these constants when model.js moves, then rerun gen_svgs.py.
"""

import math

GRID_LITERAL, GRID_MOTIF, GRID_MOTIF_EXC = 0, 1, 2
GRID_GROUP_4, GRID_GROUP_8, GRID_GROUP_16 = 3, 4, 5
GRID_SPARSE, GRID_COPY_PREV = 6, 7

NAMES = {GRID_LITERAL: "LITERAL", GRID_MOTIF: "MOTIF", GRID_MOTIF_EXC: "MOTIF_EXC",
         GRID_GROUP_4: "GROUP_4", GRID_GROUP_8: "GROUP_8", GRID_GROUP_16: "GROUP_16",
         GRID_SPARSE: "SPARSE", GRID_COPY_PREV: "COPY_PREV"}

# (code, bits). A complete prefix code: the lengths satisfy Kraft's equality,
# which model.js asserts at load time and which is checked at the end of this
# file for the same reason.
TAGS = {GRID_MOTIF: (0b00, 2), GRID_SPARSE: (0b01, 2), GRID_GROUP_8: (0b100, 3),
        GRID_MOTIF_EXC: (0b101, 3), GRID_COPY_PREV: (0b110, 3),
        GRID_LITERAL: (0b1110, 4), GRID_GROUP_4: (0b11110, 5),
        GRID_GROUP_16: (0b11111, 5)}

MOTIF_PERIOD_BITS, MOTIF_PERIODS = 2, [2, 4, 8, 16]
MOTIF_EXC_PERIOD_BITS, MOTIF_EXC_PERIODS = 4, [2, 3, 4, 6, 8, 12, 16, 24, 32]
MOTIF_EXC_COUNT_BITS = 3
MAX_MOTIF_EXC = (1 << MOTIF_EXC_COUNT_BITS) - 1
SPARSE_COUNT_BITS = 4
MAX_SPARSE_HITS = (1 << SPARSE_COUNT_BITS) - 1
GROUP_SIZES = {GRID_GROUP_4: 4, GRID_GROUP_8: 8, GRID_GROUP_16: 16}
VAR_CHUNK_BITS = 3

INF = float("inf")


def bits_for(bound):
    return max(1, math.ceil(math.log2(bound)))


def motif_period(row, n):
    """The shortest period the row tiles at, or 0. A period as long as the row
    is not one: model.js stops before it, since it would write the row flat."""
    for period in MOTIF_PERIODS:
        if period >= n:
            break
        if all(bool(row[i]) == bool(row[i % period]) for i in range(period, n)):
            return period
    return 0


def motif_exc_pos_bits(n, period):
    return bits_for(n - period)


def motif_exc_plan(row, n):
    """Cheapest motif-with-exceptions plan, or None if every period leaves too
    many steps to write out."""
    best = None
    for idx, period in enumerate(MOTIF_EXC_PERIODS):
        if period >= n:
            break
        pos = [i - period for i in range(period, n)
               if bool(row[i]) != bool(row[i % period])]
        if len(pos) > MAX_MOTIF_EXC:
            continue
        cost = (MOTIF_EXC_PERIOD_BITS + period + MOTIF_EXC_COUNT_BITS +
                len(pos) * motif_exc_pos_bits(n, period))
        if best is None or cost < best["cost"]:
            best = {"period_idx": idx, "period": period, "positions": pos, "cost": cost}
    return best


def sparse_hits(row, n):
    """The steps that play, or None if there are too many to name one at a time."""
    hits = []
    for i in range(n):
        if row[i]:
            if len(hits) == MAX_SPARSE_HITS:
                return None
            hits.append(i)
    return hits


def group_repeats(row, n, start, size):
    return all(bool(row[i]) == bool(row[i - size])
               for i in range(start, min(start + size, n)))


def group_cost(row, n, size):
    num_bits = min(size, n)
    for start in range(size, n, size):
        num_bits += 1
        if not group_repeats(row, n, start, size):
            num_bits += min(size, n - start)
    return num_bits


def choose(row, n, prev_row=None):
    """The scheme model.js writes this row in, and what it costs with its tag.

    Returns (scheme, total_bits, costs, total_fn). Ties go to the plainest
    scheme that holds the row, which is why the comparison below is strict.
    """
    period = motif_period(row, n)
    exc = motif_exc_plan(row, n)
    hits = sparse_hits(row, n)
    matches = (prev_row is not None and
               all(bool(row[i]) == bool(prev_row[i]) for i in range(n)))

    costs = {
        GRID_LITERAL: n,
        GRID_MOTIF: (MOTIF_PERIOD_BITS + period) if period else INF,
        GRID_MOTIF_EXC: exc["cost"] if exc else INF,
        GRID_GROUP_4: group_cost(row, n, 4),
        GRID_GROUP_8: group_cost(row, n, 8),
        GRID_GROUP_16: group_cost(row, n, 16),
        GRID_SPARSE: (SPARSE_COUNT_BITS + len(hits) * bits_for(n))
                     if hits is not None else INF,
        GRID_COPY_PREV: 0 if matches else INF,
    }

    def total(scheme):
        return costs[scheme] + TAGS[scheme][1]

    scheme = GRID_LITERAL
    for cand in [GRID_MOTIF, GRID_MOTIF_EXC, GRID_GROUP_4, GRID_GROUP_8,
                 GRID_GROUP_16, GRID_SPARSE, GRID_COPY_PREV]:
        if total(cand) < total(scheme):
            scheme = cand
    return scheme, total(scheme), costs, total


def tag_string(scheme):
    code, bits = TAGS[scheme]
    return format(code, "0" + str(bits) + "b")


def var_chunks(v):
    """The 3-bit chunks write_var splits a value into, least significant first."""
    out = []
    while v > 0:
        out.append(v % (1 << VAR_CHUNK_BITS))
        v //= (1 << VAR_CHUNK_BITS)
    return out


def var_bits(v):
    """What write_var spends on a value: every chunk carries a bit saying
    another one follows, and a final bit says none does. So 4n+1, and a lone
    bit for zero."""
    return len(var_chunks(v)) * (VAR_CHUNK_BITS + 1) + 1


def var_string(v):
    out = []
    for chunk in var_chunks(v):
        out.append("1")
        out.append(format(chunk, "0" + str(VAR_CHUNK_BITS) + "b"))
    out.append("0")
    return " ".join(out)


def lane_bits(gap, block):
    """What encode_lane spends on a lane holding one block: the bit saying the
    lane is used, the gap before the block, the block's length written one
    lower, and the zero gap that ends it."""
    return 1 + var_bits(gap) + var_bits(block - 1) + var_bits(0)


# The prefix code has to stay complete, the same check model.js makes
assert abs(sum(2.0 ** -bits for _, bits in TAGS.values()) - 1.0) < 1e-9


if __name__ == "__main__":
    rows = [
        ("REPEAT MOTIF",   "1000100010001000", None),
        ("SPARSE HITS",    "0000000100000000", None),
        ("LITERAL BITMAP", "1011010001011001", None),
        ("COPY PREV ROW",  "1000100010001000", "1000100010001000"),
    ]

    print("=== how each row of the figure is written (16 steps) ===")
    for label, bits, prev in rows:
        row = [int(c) for c in bits]
        prev_row = [int(c) for c in prev] if prev else None
        scheme, tot, costs, total = choose(row, 16, prev_row)
        print(f"{label:15} {bits}  {NAMES[scheme]:10} "
              f"tag={tag_string(scheme):5} payload={costs[scheme]:2}  "
              f"TOTAL={tot} bits")

    gap, block, cells = 32, 16, 128
    print()
    print(f"=== timeline lane: {cells} cells, on for cells "
          f"{gap} to {gap + block - 1} ===")
    print(f"lane-used flag          1 bit")
    print(f"write_var(gap {gap})       {var_bits(gap)} bits   {var_string(gap)}")
    print(f"write_var(len-1 {block - 1})    {var_bits(block - 1)} bits   "
          f"{var_string(block - 1)}")
    print(f"write_var(0) stop       {var_bits(0)} bit")
    print(f"TOTAL = {lane_bits(gap, block)} bits, against {cells} raw")

#!/usr/bin/env python3
"""Generate the SVG figures for this post. Writes them next to this file.

The bit counts on the figures are not written out here. They come from
verify.py, which ports the cost model in groovie's model.js, so that a change
to the encoding shows up in the drawings rather than quietly making them wrong.
The prose breakdowns ("2 tag + 2 period + 4 motif steps") are written by hand,
and asserted against the computed total, so one can't drift from the other.

Drawing constraints come from site/style.css:
  - light only, white background, greys plus #a00, DejaVu Sans Mono
  - 820px content column, figure img at 95% of it, capped at 500px tall
  - no em dashes, en dashes or ellipses anywhere that reaches the HTML,
    since publish.sh rejects them
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# Everything beside this file is copied to the built site as-is, and a
# __pycache__ left by the import below would be copied along with it
sys.dont_write_bytecode = True

import verify as V

FONT = "'DejaVu Sans Mono','Lucida Console',Menlo,Consolas,monospace"
INK, SUB, MID, LINE, OFF, ON, BG = "#000", "#444", "#777", "#999", "#D2D2D2", "#a00", "#fff"
PALE = "#dd9999"      # the reused row, still clearly red
HAIR, STROKE = 1.2, 1.6

W = 780
STEPS = 16


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n' + body + '</svg>\n')


def text(x, y, s, size=13, fill=INK, anchor="start", weight=None, tl=None, ls=None):
    t = (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
         f'fill="{fill}" text-anchor="{anchor}"')
    if weight:
        t += f' font-weight="{weight}"'
    if ls:
        t += f' letter-spacing="{ls}"'
    if tl:
        t += f' textLength="{tl:.1f}" lengthAdjust="spacingAndGlyphs"'
    return t + f'>{s}</text>\n'


def rect(x, y, w, h, fill, stroke=None, sw=HAIR, rx=0):
    s = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"'
    if rx:
        s += f' rx="{rx}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}"'
    return s + '/>\n'


def line(x1, y1, x2, y2, stroke=MID, sw=HAIR, dash=None):
    s = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
         f'stroke="{stroke}" stroke-width="{sw}"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s + '/>\n'


def arrow_down(x, y1, y2, stroke=MID):
    return (line(x, y1, x, y2 - 9, stroke, 2.2) +
            f'<path d="M {x-6:.1f} {y2-10:.1f} L {x:.1f} {y2:.1f} '
            f'L {x+6:.1f} {y2-10:.1f} Z" fill="{stroke}"/>\n')


def bracket(x1, x2, y, label, size=12, fill=SUB):
    b = line(x1, y, x2, y, MID, STROKE)
    b += line(x1, y - 5, x1, y + 5, MID, STROKE)
    b += line(x2, y - 5, x2, y + 5, MID, STROKE)
    b += text((x1 + x2) / 2, y + 19, label, size, fill, "middle")
    return b


def step_grid(gx, gy, bits, cell, h=None, ghost=False, inset=1):
    """One row of step cells on a fixed pitch.

    inset is horizontal only. The pitch is what lines a row up with the ruler
    above it and the bits written below it, so widening the gap between cells
    shrinks the drawn cell inside its pitch rather than moving it.
    """
    h = h if h else cell
    b = ""
    for i, ch in enumerate(bits):
        cx = gx + i * cell
        if ch == "1":
            b += rect(cx + inset, gy + 1, cell - 2 * inset, h - 2,
                      PALE if ghost else ON, MID if ghost else None, HAIR, 2)
        else:
            b += rect(cx + inset, gy + 1, cell - 2 * inset, h - 2,
                      BG if ghost else OFF, LINE, HAIR, 2)
    return b


# ---------------------------------------------------------------- figure 1
def fig_pattern_grid():
    cell, n = 36, STEPS
    gw = n * cell
    labw, gap, annw = 66, 12, 58
    x0 = (W - (labw + gap + gw + 14 + annw)) / 2
    gx = x0 + labw + gap

    rows = [("KICK",  "1000100010001000"),
            ("SNARE", "0000100000001000"),
            ("HAT",   "1010101010101010")]

    b = ""
    for i in range(0, n, 4):
        b += text(gx + i * cell + cell / 2, 30, str(i + 1), 12, MID, "middle")

    ytop = 42
    for ri, (lab, bits) in enumerate(rows):
        ry = ytop + ri * (cell + 3)
        b += text(x0 + labw, ry + cell / 2 + 5, lab, 13, INK, "end")
        # 2.5 leaves a 5px gap between cells, the same gap the rows have
        # vertically, so the grid reads as evenly spaced in both directions
        b += step_grid(gx, ry, bits, cell, inset=2.5)

    gbot = ytop + 3 * (cell + 3) - 3
    for i in range(4, n, 4):
        b += line(gx + i * cell, ytop - 5, gx + i * cell, gbot + 5, MID, HAIR)

    b += arrow_down(gx + gw / 2, gbot + 16, gbot + 48)

    by = gbot + 74
    for ri, (lab, bits) in enumerate(rows):
        ry = by + ri * 26
        b += text(x0 + labw, ry, lab, 13, MID, "end")
        for i, ch in enumerate(bits):
            b += text(gx + i * cell + cell / 2, ry, ch, 15,
                      ON if ch == "1" else MID, "middle",
                      weight="bold" if ch == "1" else None)
        b += text(gx + gw + 14, ry, f"{n} bits", 12, SUB)

    b += text(W / 2, by + 3 * 26 + 16,
              f"{len(rows)} rows x {n} steps = {len(rows) * n} bits",
              13, INK, "middle")

    return svg(W, int(by + 3 * 26 + 38), b)


# ---------------------------------------------------------------- figure 2
# Each panel names a row, the row before it where the scheme needs one, and how
# its bits are spent. The parts are prose, but they have to add up to what
# verify.py says the row costs, which is asserted below.
PANELS = [
    ("REPEAT MOTIF",   "1000100010001000", None,
     [(2, "tag"), (2, "period"), (4, "motif steps")], ""),
    ("SPARSE HITS",    "0000000100000000", None,
     [(2, "tag"), (4, "count"), (4, "position")], ""),
    ("LITERAL BITMAP", "1011010001011001", None,
     [(4, "tag"), (16, "steps written out")], ""),
    ("COPY PREV ROW",  "1000100010001000", "1000100010001000",
     [(3, "tag")], ", and nothing else at all"),
]


def panel_facts():
    """Work out what each panel draws, and check the prose against the model."""
    out = []
    for name, bits, prev, parts, suffix in PANELS:
        row = [int(c) for c in bits]
        prev_row = [int(c) for c in prev] if prev else None
        scheme, total, _, _ = V.choose(row, STEPS, prev_row)

        claimed = sum(n for n, _ in parts)
        assert claimed == total, (
            f"{name}: breakdown adds to {claimed} bits but the encoder "
            f"writes this row in {total}")
        assert parts[0][0] == V.TAGS[scheme][1], (
            f"{name}: breakdown starts with a {parts[0][0]} bit tag but "
            f"{V.NAMES[scheme]} is tagged in {V.TAGS[scheme][1]}")

        breakdown = " + ".join(f"{n} {label}" for n, label in parts) + suffix
        out.append((name, V.tag_string(scheme), bits, breakdown,
                    f"{total} bits", prev is not None))
    return out


def fig_row_strategies():
    cell, n = 26, STEPS
    gw = n * cell
    gx = 244
    panel_h = 72
    top = 56

    b = ""
    b += text(24, 32, "SCHEME", 11.5, MID, ls="1")
    b += text(gx, 32, f"ROW ({n} STEPS)", 11.5, MID, ls="1")
    b += text(760, 32, "COST", 11.5, MID, "end", ls="1")
    b += line(24, 40, 760, 40, MID, STROKE)

    panels = panel_facts()
    for pi, (name, tag, bits, brk, cost, ghost) in enumerate(panels):
        py = top + pi * panel_h
        b += text(24, py + 18, name, 12.5, INK, weight="bold")
        b += text(24, py + 37, f"tag {tag}", 11.5, ON, weight="bold")
        b += text(24, py + 53, brk, 10.5, SUB)
        b += step_grid(gx, py + 6, bits, cell, ghost=ghost)
        b += text(760, py + 26, cost, 16, ON, "end", weight="bold")
        if pi < len(panels) - 1:
            b += line(24, py + panel_h - 8, 760, py + panel_h - 8, LINE, HAIR)

    ry = top + (len(panels) - 1) * panel_h
    b += text(gx + gw / 2, ry + 50,
              "identical to the same row in the pattern before it",
              11.5, MID, "middle")

    shortest = min(bits for _, bits in V.TAGS.values())
    longest = max(bits for _, bits in V.TAGS.values())
    h = ry + panel_h + 16
    b += line(24, h - 18, 760, h - 18, MID, STROKE)
    b += text(24, h + 2,
              f"the tags are a prefix code: the two commonest schemes are "
              f"named in {shortest} bits, the rarest in {longest}", 11, MID)

    return svg(W, int(h + 16), b)


# ---------------------------------------------------------------- figure 3
def fig_timeline_rle():
    bars, cell = 128, 5.2
    gw = bars * cell
    gx = (W - gw) / 2
    on_start, on_len = 32, 16

    b = ""
    for i in range(0, bars + 1, 16):
        x = gx + i * cell
        b += line(x, 30, x, 38, MID, HAIR)
        b += text(x, 24, str(i), 11, MID, "middle")

    # The strip is drawn as solid runs rather than 128 outlined cells, which at
    # this width reads as stripes rather than as a timeline. The separators sit
    # every 16 cells, on the ruler ticks, and the block lands between two of
    # them so none of them cuts through it.
    gy, gh = 42, 30
    b += rect(gx, gy, gw, gh, OFF)
    b += rect(gx + on_start * cell, gy, on_len * cell, gh, ON)
    for i in range(16, bars, 16):
        b += line(gx + i * cell, gy, gx + i * cell, gy + gh, MID, HAIR)
    b += rect(gx, gy, gw, gh, "none", MID, STROKE)

    b += bracket(gx, gx + on_start * cell, gy + gh + 12, f"gap {on_start}")
    b += bracket(gx + on_start * cell, gx + (on_start + on_len) * cell,
                 gy + gh + 12, f"block {on_len}", fill=ON)
    b += text(gx + (on_start + on_len) * cell + 14, gy + gh + 17,
              "the lane stops at its last active cell", 11.5, MID)

    b += arrow_down(W / 2, gy + gh + 46, gy + gh + 78)

    gap_b, blk_b = V.var_bits(on_start), V.var_bits(on_len - 1)
    stop_b = V.var_bits(0)
    total = V.lane_bits(on_start, on_len)
    assert total == 1 + gap_b + blk_b + stop_b

    y = gy + gh + 100
    b += text(W / 2, y, f"{bars} bits as a raw bitmap", 13, MID, "middle")
    b += text(W / 2, y + 26,
              f"1 used + {gap_b} gap + {blk_b} block + {stop_b} stop "
              f"= {total} bits", 16, ON, "middle", weight="bold")

    # How the block length is written
    bx, by, bw, bh = 70, y + 48, 640, 132
    b += rect(bx, by, bw, bh, BG, MID, STROKE, 4)
    b += text(bx + 20, by + 24,
              f"a block always holds a cell, so its length is written one "
              f"lower: {on_len} goes out as {on_len - 1}", 11.5, SUB)

    chunks = V.var_chunks(on_len - 1)
    cw, chh, grp_gap = 40, 30, 16
    groups = len(chunks)
    total_w = groups * (4 * cw) + (groups - 1) * grp_gap + grp_gap + cw
    cx = bx + (bw - total_w) / 2
    for gi, payload in enumerate(chunks):
        b += rect(cx, by + 44, cw, chh, ON, None, HAIR, 3)
        b += text(cx + cw / 2, by + 64, "1", 15, BG, "middle", weight="bold")
        for bi in range(V.VAR_CHUNK_BITS):
            px = cx + (bi + 1) * cw
            bit = (payload >> (V.VAR_CHUNK_BITS - 1 - bi)) & 1
            b += rect(px, by + 44, cw, chh, OFF, LINE, HAIR, 3)
            b += text(px + cw / 2, by + 64, str(bit), 15, INK, "middle")
        b += text(cx + 2 * cw, by + 90,
                  f"chunk {gi + 1} = {payload}", 11, MID, "middle")
        cx += 4 * cw + grp_gap

    b += rect(cx, by + 44, cw, chh, OFF, LINE, HAIR, 3)
    b += text(cx + cw / 2, by + 64, "0", 15, INK, "middle", weight="bold")
    b += text(cx + cw / 2, by + 90, "stop", 11, MID, "middle")

    # Two anchored runs rather than one padded string: SVG collapses runs of
    # spaces, so padding a single text element does not hold a column
    b += text(bx + 20, by + 116, "red = another chunk follows", 11.5, SUB)
    sums = " + ".join(
        f"{c}" if i == 0 else f"{c} x {8 ** i}" for i, c in enumerate(chunks))
    b += text(bx + bw - 20, by + 116,
              f"{on_len - 1} = {sums} = {blk_b} bits", 11.5, SUB, "end")

    return svg(W, int(by + bh + 22), b)


# ---------------------------------------------------------------- figure 4
def fig_url_anatomy():
    fs, cwid = 15, 8.9
    segs = [
        ("https://maximecb.github.io/groovie/#", SUB, "static host, no backend"),
        ("the_amen_break",                       INK, "song title"),
        ("/",                                    MID, None),
        ("BgBA_MEUQOLAXGGsElCXs4a1qAwaDUHg",     ON,  "the entire project"),
    ]
    total = sum(len(s) for s, _, _ in segs)
    x = (W - total * cwid) / 2
    y = 50

    b = ""
    cur = x
    marks = []
    for s, color, lab in segs:
        # textLength pins each run to the width it was laid out at, so the
        # brackets stay under their segment whatever monospace font is around
        wid = len(s) * cwid
        b += text(cur, y, s, fs, color, tl=wid,
                  weight="bold" if color in (ON, INK) else None)
        if lab:
            marks.append((cur, cur + wid, lab))
        cur += wid

    for x1, x2, lab in marks:
        b += bracket(x1, x2, y + 16, lab)

    b += text(W / 2, y + 68,
              "no server, no account, no database: the link is the file",
              13, INK, "middle")

    return svg(W, int(y + 90), b)


FIGURES = [("url-anatomy.svg", fig_url_anatomy),
           ("pattern-grid.svg", fig_pattern_grid),
           ("timeline-rle.svg", fig_timeline_rle),
           ("row-strategies.svg", fig_row_strategies)]

# Characters publish.sh refuses to ship, checked here rather than found later
REJECTED = ("—", "–", "…", "“", "”", "‘", "’")

if __name__ == "__main__":
    for name, fn in FIGURES:
        data = fn()
        for bad in REJECTED:
            assert bad not in data, f"{name} contains a rejected character"
        with open(os.path.join(HERE, name), "w") as f:
            f.write(data)
        print(f"{name:22} {len(data):6} bytes")

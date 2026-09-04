#!/usr/bin/env python3
"""Generate the SVG figures for this post. Writes them next to this file.

  speedup.svg    per benchmark speedup, with the geomean called out
  memory.svg     per benchmark peak RSS reduction, same shape
  value-repr.svg what the low bits of a Value mean
  flonum.svg     how rotating a double by 4 lands a tag in the low bits
  cover.png      the social card, via cover.svg

The two charts read results.json, so ./bench.py has to have run first.

NO PADDING AROUND THE DRAWINGS. The browser scales the whole canvas to fit the
text column, so every blank pixel inside the canvas is a pixel the drawing does
not get. Slack at the sides makes the figure look narrow. Slack at the top or
bottom is worse: it pushes the drawing away from the paragraph it belongs to
and shrinks it as well, since both dimensions scale together. So:

  - a figure's height is whatever its last element reaches, plus MARGIN. Never
    round it up to a nicer number, and never pad one figure to match another
  - ink runs out to MARGIN on the left and on the right. A row that would be
    narrower than that is widened rather than centred inside a wider gutter
  - MARGIN is there so glyphs and stroke widths do not touch the canvas edge.
    It is not visual breathing room. The gap between a figure and the text
    around it belongs in style.css, where it applies to photos too

Drawing constraints come from site/style.css:
  - light only, white background, DejaVu Sans Mono
  - the text column is 772px, so the figures render 1:1 and are not scaled
  - capped at 500px tall, so HEIGHT_CAP below is checked, not trusted
  - no em dashes, en dashes or ellipses anywhere that reaches the HTML,
    since publish.sh rejects them

Sentences are capitalised. Lowercase text is identifiers: benchmark names,
commit hashes, and field names out of value.rs.

Colour carries meaning. GREEN is the new representation winning and RED is it
losing, in both charts. In the two diagrams the hue names a type, so fixnums,
flonums, pointers and immediates each get their own and keep it across both
figures: a flonum is violet everywhere it appears.

The cover is the exception to everything above. It is not a figure in the
text, it is the card that shows up on other people's timelines, so it is
1200x630 and is rasterised to PNG.
"""

import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

FONT = "'DejaVu Sans Mono','Lucida Console',Menlo,Consolas,monospace"

INK, SUB, MID, LINE, BG = "#111", "#444", "#777", "#bbb", "#fff"
RED, GREEN, BLUE = "#cc2222", "#0e8a52", "#1560c0"
GDARK = "#0a6b40"
DEEP = "#0f4b96"
PALE = "#cfe0f5"
SHELL, SHELL_HDR = "#eef1f5", "#dde3ea"
GPALE = "#d6ece0"
RPALE = "#f6dada"

# Flonums get their own hue so they never read as a fixnum
VIOLET, VDARK, VPALE = "#6b3fa0", "#57318a", "#e7dcf6"

HAIR, STROKE = 1.2, 1.6

W = 772
MARGIN = 14
HEIGHT_CAP = 500

MONO_ADV = 0.6022

LAB_SIZE = 11.5
LAB_GAP = 10


def text_width(s, size):
    return len(s) * size * MONO_ADV


def esc(s):
    """Escape for XML text content. Captions here contain << and &."""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(w, h, body, defs="", cap=True):
    assert not cap or h <= HEIGHT_CAP, f"{h}px tall, over the {HEIGHT_CAP}px cap"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n'
            + (f'<defs>\n{defs}</defs>\n' if defs else '')
            + f'<rect width="{w}" height="{h}" fill="{BG}"/>\n' + body + '</svg>\n')


def text(x, y, s, size=13, fill=INK, anchor="start", weight=None, ls=None):
    t = (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
         f'fill="{fill}" text-anchor="{anchor}"')
    if weight:
        t += f' font-weight="{weight}"'
    if ls:
        t += f' letter-spacing="{ls}"'
    return t + f'>{esc(s)}</text>\n'


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


def arrow(x1, y1, x2, y2, stroke=MID, sw=1.5, head=9):
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    bx, by = x2 - ux * head, y2 - uy * head
    px, py = -uy * head * 0.42, ux * head * 0.42
    return (line(x1, y1, bx, by, stroke, sw) +
            f'<path d="M {bx + px:.1f} {by + py:.1f} L {x2:.1f} {y2:.1f} '
            f'L {bx - px:.1f} {by - py:.1f} Z" fill="{stroke}"/>\n')


def curve_arrow(x1, y1, cx, cy, x2, y2, stroke=MID, sw=2.0, head=10):
    """Quadratic from one point to another, with the head at the far end."""
    # Direction of the curve as it arrives, for orienting the head
    dx, dy = x2 - cx, y2 - cy
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    ex, ey = x2 - ux * head, y2 - uy * head
    px, py = -uy * head * 0.42, ux * head * 0.42
    return (f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {ex:.1f} {ey:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="{sw}"/>\n'
            f'<path d="M {ex + px:.1f} {ey + py:.1f} L {x2:.1f} {y2:.1f} '
            f'L {ex - px:.1f} {ey - py:.1f} Z" fill="{stroke}"/>\n')


def haloed(x, y, s, size, fill, anchor="start", weight=None):
    """Text on a white pad, for labels that land on the reference line.

    Drawing the label after the line is not enough on its own: the glyphs
    cover the dashes they sit on, but the line still shows through the gaps
    between letters and reads as a strike through.
    """
    w = text_width(s, size)
    x0 = x - (w if anchor == "end" else 0) - 2
    return (rect(x0, y - size + 1.5, w + 4, size + 2, BG)
            + text(x, y, s, size, fill, anchor, weight))


def heading(y, s):
    assert text_width(s, 13) <= W - 2 * MARGIN, f"heading too wide: {s}"
    return text(MARGIN, y, s, 13, INK, weight="bold")


def note(y, s, x=MARGIN):
    assert text_width(s, 11.5) <= W - 2 * MARGIN, f"note too wide: {s}"
    return text(x, y, s, 11.5, SUB)


# ---------------------------------------------------------------- charts

def nice_ticks(lo, hi, step):
    t, out = math.ceil(lo / step) * step, []
    while t <= hi + 1e-9:
        out.append(round(t, 6))
        t += step
    return out


def bar_chart(rows, summary, title, sub, unit_label, fname,
              refline=1.0, step=0.2, fmt=None, row_h=15.0, gap=3.5,
              lower_better=False):
    """Horizontal bars from a zero origin, against a dashed line at `refline`.

    rows is a list of (label, value, kind), where kind is "bar" for an
    ordinary benchmark and "extra" for one shown outside the summarised set.

    Bars start at zero so their lengths are comparable to each other as well
    as to the reference. The dashed line at 1.00x is what says whether a bar
    is a win, since a ratio of 1 means nothing changed.

    lower_better flips which side of the reference is green. Speedups are a
    multiple of the old speed, so more is better; peak RSS is a multiple of
    the old footprint, so 0.63x is the good direction.
    """
    fmt = fmt or (lambda v: f"{v:.2f}x")
    pitch = row_h + gap

    labels = [r[0] for r in rows] + ["geomean"]
    lab_w = max(text_width(s, LAB_SIZE) for s in labels)
    x0 = MARGIN + lab_w + LAB_GAP
    val_w = max(text_width(fmt(v), LAB_SIZE) for v in
                [r[1] for r in rows] + [summary])
    x1 = W - MARGIN - val_w - 6

    top = MARGIN + 15
    if sub:
        top += 16
    top += 26            # the tick labels sit here, clear of the subtitle

    vals = [r[1] for r in rows] + [summary, refline]
    lo, hi = 0.0, max(vals) * 1.04
    def sx(v):
        return x0 + (x1 - x0) * (v - lo) / (hi - lo)

    b = heading(MARGIN + 11, title)
    if sub:
        b += note(MARGIN + 29, sub)

    body_top = top
    body_bot = top + len(rows) * pitch + 10 + pitch

    # The reference line is drawn last, over the bars, further down
    for t in nice_ticks(lo, hi, step):
        if abs(t - refline) < 1e-9:
            continue          # the reference line carries its own label
        b += line(sx(t), body_top - 8, sx(t), body_bot - gap, LINE,
                  HAIR, "3 3")
        b += text(sx(t), body_top - 12, fmt(t), 10.5, MID, "middle")

    # Value labels are collected and emitted after the reference line, so a
    # bar that ends near 1.00x does not get its number struck through
    vlabels = []

    y = body_top
    for lab, val, kind in rows:
        win = (val <= refline) if lower_better else (val >= refline)
        fill, edge = (GPALE, GDARK) if win else (RPALE, RED)
        if kind == "extra":
            fill, edge = SHELL, MID
        left, right = sx(0.0), sx(val)
        b += rect(left, y, max(right - left, 0.8), row_h, fill, edge, HAIR)
        b += text(x0 - LAB_GAP, y + row_h / 2 + 4, lab, LAB_SIZE,
                  MID if kind == "extra" else INK, "end")
        vlabels.append(haloed(right + 6, y + row_h / 2 + 4, fmt(val),
                              LAB_SIZE, MID if kind == "extra" else edge))
        y += pitch

    y += 4
    b += line(MARGIN, y - 2, W - MARGIN, y - 2, LINE, HAIR)
    y += 6
    left, right = sx(0.0), sx(summary)
    b += rect(left, y, max(right - left, 0.8), row_h, GREEN, GDARK, HAIR)
    b += text(x0 - LAB_GAP, y + row_h / 2 + 4, "geomean", LAB_SIZE, INK,
              "end", weight="bold")
    vlabels.append(haloed(right + 6, y + row_h / 2 + 4, fmt(summary),
                          LAB_SIZE, GDARK, weight="bold"))
    y += row_h

    b += line(sx(refline), body_top - 8, sx(refline), y + 4, INK, STROKE, "5 4")
    b += text(sx(refline), body_top - 12, fmt(refline), 10.5, INK, "middle",
              weight="bold")
    b += "".join(vlabels)

    lines = [unit_label] if isinstance(unit_label, str) else list(unit_label)
    ly = y + 14
    for ln in lines:
        b += note(ly, ln)
        ly += 16
    h = round(ly - 16 + 5 + MARGIN)

    open(os.path.join(HERE, fname), "w").write(svg(W, h, b))
    print(f"{fname}: {W}x{h}")


BENCH_ORDER = [
    "alloc_objs", "arr_get", "binary_tree", "fft", "fib", "for_loop",
    "gc_alloc_speed", "gc_many_objs", "host_calls", "linked_list",
    "matrix_vec_mult", "mlp", "nbody", "obj_get", "ping_pong", "quicksort",
    "sha256_fixed",
]


def charts():
    with open(os.path.join(HERE, "results.json")) as f:
        data = json.load(f)
    bm, summ = data["benchmarks"], data["summary"]
    skipped = set(summ["too_short_for_timing"])

    rows = [(n, bm[n]["speedup"], "bar")
            for n in BENCH_ORDER if n not in skipped]
    # Shown but not summarised, the same way the memory chart carries it:
    # three million boxed integers cost it speed and it still came out ahead.
    # It sorts in with the rest; the grey is what says it is not counted
    if "sha256_unfixed" in bm:
        rows.append(("sha256_unfixed", bm["sha256_unfixed"]["speedup"], "extra"))
    rows.sort(key=lambda r: -r[1])
    bar_chart(
        rows, summ["speedup_geomean"],
        "Speedup, boxed representation against the tagged enum",
        f"Median of {summ['rounds']} interleaved rounds, higher is faster.",
        ["Measured on a MacBook Air M5, ac75356 against 6b71f8c.",
         "The geomean covers the 15 benchmarks, not sha256_unfixed."],
        "speedup.svg", step=0.2)

    # Peak RSS as a multiple of what it was, so 0.63x reads as "the new one
    # needs 63% of the memory". Smallest first, since small is the win here.
    def frac(n):
        d = bm[n]
        return d["rss_new"] / d["rss_old"]

    rows = [(n, frac(n), "bar") for n in BENCH_ORDER]
    if "sha256_unfixed" in bm:
        rows.append(("sha256_unfixed", frac("sha256_unfixed"), "extra"))
    rows.sort(key=lambda r: r[1])
    bar_chart(
        rows, 1.0 / summ["rss_geomean"],
        "Peak RSS, boxed representation against the tagged enum",
        "Median of the same rounds. Lower is less memory used.",
        "The geomean covers the 17 benchmarks, not sha256_unfixed.",
        "memory.svg", step=0.2, lower_better=True)


# ------------------------------------- shared bit layout drawing helpers

GRID = "#c9c9c9"     # a bit boundary inside a field, not a field boundary

# Numbering all 64 positions puts the labels 10px apart and reads as noise,
# so the high bits get only their byte boundaries. The low byte is numbered
# in full, since that is where the tag and the subtag are.
RULER_BITS = [63, 56, 48, 40, 32, 24, 16] + list(range(8, -1, -1))


def bit_x(x0, bw, bit):
    """Left edge of a bit, counting down from 63 at the left."""
    return x0 + (63 - bit) * bw


def bit_ruler(x0, bw, y, size=9.0, tick_to=None, bits=None):
    """Number selected bit positions, each centred on the bit it names."""
    s = ""
    for bit in (RULER_BITS if bits is None else bits):
        cx = bit_x(x0, bw, bit) + bw / 2
        s += text(cx, y, str(bit), size, SUB, "middle")
        if tick_to is not None:
            s += line(cx, y + 3, cx, tick_to, LINE, HAIR)
    return s


def bit_grid(x0, bw, y, h, hi=63, lo=0):
    """A hairline on every bit boundary inside a bar."""
    s = ""
    for bit in range(hi, lo, -1):
        x = bit_x(x0, bw, bit) + bw
        s += line(x, y, x, y + h, GRID, 0.7)
    return s


def bit_digits(x0, bw, y, h, hi, s, tc="#fff", size=11.5):
    """A literal bit pattern, one character centred on each bit it occupies."""
    out = ""
    for i, ch in enumerate(s):
        out += text(bit_x(x0, bw, hi - i) + bw / 2, y + h / 2 + 4, ch,
                    size, tc, "middle", weight="bold")
    return out


def bit_field_rect(x0, bw, y, h, hi, lo, fill, edge):
    """The block for one field. Drawn before the grid, which sits over it."""
    return rect(bit_x(x0, bw, hi), y, (hi - lo + 1) * bw, h, fill, edge, HAIR)


def bit_field_label(x0, bw, y, h, hi, lo, label, tc=INK, size=11.5, pad=0):
    """A field's caption. Drawn after the grid so the lines run behind it."""
    x, w = bit_x(x0, bw, hi), (hi - lo + 1) * bw
    assert text_width(label, size) <= w - 4, \
        f"{label!r} does not fit {hi}..{lo}"
    if pad:
        return text(x + pad, y + h / 2 + 4, label, size, tc, "start")
    return text(x + w / 2, y + h / 2 + 4, label, size, tc, "middle")


# ------------------------------------------------------- value-repr.svg

def value_repr():
    """The 64-bit word, and what each tag in the low bits means."""
    ROW_H, GAP = 30.0, 9.0
    pitch = ROW_H + GAP

    # Every field is drawn at its true width in bits, so the tag reads as the
    # 2 or 3 bits it actually is rather than as a block big enough to letter
    rows = [
        # name, then the fields as (hi, lo, fill, edge, label, text colour)
        ("fixnum", [
            (63, 2, GPALE, GDARK,
             "Signed integer (62 bits), stored as n << 2", INK),
            (1, 0, GDARK, GDARK, "00", "#fff")]),
        ("pointer", [
            (63, 3, PALE, DEEP,
             "Heap block pointer (61 bits), compared by identity", INK),
            (2, 0, DEEP, DEEP, "001", "#fff")]),
        ("pointer", [
            (63, 3, PALE, DEEP,
             "Heap block pointer (61 bits), compared by value", INK),
            (2, 0, DEEP, DEEP, "011", "#fff")]),
        ("immediate", [
            (63, 8, SHELL, MID, "Payload (56 bits)", INK),
            (7, 3, SHELL_HDR, MID, "subtag", INK),
            (2, 0, MID, MID, "101", "#fff")]),
        # The flonum is one field: the rotation encodes the double across the
        # whole word, and bits 1..0 reading 10 is a consequence of it rather
        # than a field set aside. They are marked, not carved out.
        ("flonum", [
            (63, 0, VPALE, VDARK,
             "rotl(bits + BIAS, 4), all 64 bits, see below", INK)]),
    ]

    lab_w = max(text_width(n, LAB_SIZE) for n, _ in rows)
    x0 = MARGIN + lab_w + LAB_GAP
    x1 = W - MARGIN
    bw = (x1 - x0) / 64.0

    top = MARGIN + 13 + 18 + 14

    b = heading(MARGIN + 11,
                "A Value is one 64-bit word, and the low bits say what it is")
    b += bit_ruler(x0, bw, top - 10, tick_to=top,
                   bits=[63] + list(range(7, -1, -1)))

    y = top
    for name, fields in rows:
        for hi, lo, fill, edge, _, _ in fields:
            b += bit_field_rect(x0, bw, y, ROW_H, hi, lo, fill, edge)
        b += bit_grid(x0, bw, y, ROW_H)
        for hi, lo, _, edge, label, tc in fields:
            if set(label) <= {"0", "1"}:
                # A literal tag: one digit per bit, so its width is its length
                b += bit_digits(x0, bw, y, ROW_H, hi, label, tc)
            else:
                # The wide payload captions read better ranged left
                pad = 8 if hi - lo > 20 else 0
                b += bit_field_label(x0, bw, y, ROW_H, hi, lo, label, tc,
                                     10.5 if label == "subtag" else 11.5, pad)
            b += rect(bit_x(x0, bw, hi), y, (hi - lo + 1) * bw, ROW_H,
                      "none", edge, HAIR)
        if name == "flonum":
            b += rect(bit_x(x0, bw, 1), y, 2 * bw, ROW_H, VDARK, VDARK, HAIR)
            b += bit_digits(x0, bw, y, ROW_H, 1, "10")
        b += text(x0 - LAB_GAP, y + ROW_H / 2 + 4, name, LAB_SIZE, INK, "end")
        y += pitch

    y += 2
    b += note(y + 8, "The 5-bit subtag makes the whole low byte a per-type "
                     "constant: nil is 0x05, undef 0x0D,")
    b += note(y + 24, "false 0x15, true 0x1D, Fun 0x25, Class 0x2D, "
                      "HostFn 0x35.")
    b += note(y + 46, "Bit 1 is the compare by value bit. It is set only where "
                      "equality is not a word compare:")
    b += note(y + 62, "flonums, strings and boxed numbers. So eq is a mask test "
                      "plus a word compare, and")
    b += note(y + 78, "every other combination of types falls out correct for "
                      "free.")
    h = round(y + 78 + 5 + MARGIN)

    open(os.path.join(HERE, "value-repr.svg"), "w").write(svg(W, h, b))
    print(f"value-repr.svg: {W}x{h}")


# ----------------------------------------------------------- flonum.svg

def flonum():
    """Where the bits of a double end up once it is rotated by 4."""
    b = heading(MARGIN + 11, "How a double gets a tag without losing a bit")
    b += note(MARGIN + 29,
              "Rotating left by 4 moves the top 4 bits to the bottom, and 2 "
              "of them become the tag.")

    x0, x1 = MARGIN + 48, W - MARGIN
    bw = (x1 - x0) / 64.0        # one bit
    BAR_H = 30.0

    def bx(bit):
        return bit_x(x0, bw, bit)

    def field(y, hi_bit, lo_bit, fill, edge, label, size=10.5, tc=INK):
        """Block, then the bit grid over it, then the caption over that."""
        s = bit_field_rect(x0, bw, y, BAR_H, hi_bit, lo_bit, fill, edge)
        s += bit_grid(x0, bw, y, BAR_H, hi_bit, lo_bit)
        s += rect(bx(hi_bit), y, (hi_bit - lo_bit + 1) * bw, BAR_H,
                  "none", edge, HAIR)
        if label:
            s += bit_field_label(x0, bw, y, BAR_H, hi_bit, lo_bit, label,
                                 tc, size)
        return s

    y = MARGIN + 29 + 40

    # One ruler at the top serves all three bars, since they are aligned
    b += bit_ruler(x0, bw, y - 24, tick_to=y - 17)

    # 1. the double as IEEE 754 lays it out
    b += text(MARGIN, y + BAR_H / 2 + 4, "double", LAB_SIZE, INK, "start")
    b += field(y, 63, 63, SHELL_HDR, MID, "s", 9.5)
    b += field(y, 62, 62, SHELL, MID, "", 9.5)
    b += field(y, 61, 60, VPALE, VDARK, "", 9.5)
    b += field(y, 59, 52, SHELL, MID, "", 9.5)
    b += field(y, 51, 0, SHELL, MID, "mantissa (52 bits)")
    # brace naming the exponent, which spans three of those cells
    b += line(bx(62), y - 5, bx(52) + bw, y - 5, MID, HAIR)
    b += line(bx(62), y - 5, bx(62), y, MID, HAIR)
    b += line(bx(52) + bw, y - 5, bx(52) + bw, y, MID, HAIR)
    b += text((bx(62) + bx(52) + bw) / 2, y - 9, "exponent (11 bits)", 9.5,
              MID, "middle")

    # The two bits the scheme leans on are only 2 cells wide, so the label
    # goes out to the right on a leader rather than under them
    ec = bx(61) + bw
    b += line(ec, y + BAR_H, ec, y + BAR_H + 8, VDARK, HAIR)
    b += line(ec, y + BAR_H + 8, bx(50), y + BAR_H + 8, VDARK, HAIR)
    b += text(bx(50) + 5, y + BAR_H + 12, "exponent bits 9..8", 10.0,
              VDARK, "start")

    y += BAR_H + 12 + 14

    # 2. adding BIAS is what puts a known pattern in those two bits
    bias_x = MARGIN + 140
    bias_s = ("+ BIAS (0x6810_0000_0000_0000), so those two bits read 10 "
              "for every inline double")
    assert bias_x + 12 + text_width(bias_s, 11.0) <= W - MARGIN, \
        "the BIAS line runs off the right edge"
    b += arrow(bias_x, y + 2, bias_x, y + 22, MID)
    b += text(bias_x + 12, y + 16, bias_s, 11.0, SUB, "start")
    y += 30

    # 3. the rotation itself
    b += text(MARGIN, y + BAR_H / 2 + 4, "rotl 4", LAB_SIZE, INK, "start")
    b += field(y, 63, 60, VPALE, VDARK, "63..60", 9.5)
    b += field(y, 59, 0, SHELL, MID, "everything else, untouched")
    top_c = (bx(63) + bx(60) + bw) / 2
    y_from = y + BAR_H

    y += BAR_H + 40

    # 4. where they land
    b += text(MARGIN, y + BAR_H / 2 + 4, "tagged", LAB_SIZE, INK, "start")
    b += field(y, 63, 4, SHELL, MID, "everything else, shifted up by 4")
    b += field(y, 3, 2, VPALE, VDARK, "", 9.5)
    b += field(y, 1, 0, VIOLET, VDARK, "10", 10.0, "#fff")
    low_c = (bx(3) + bx(0) + bw) / 2

    # the carry around, from the top 4 bits down to the bottom 4
    b += curve_arrow(top_c, y_from + 2, (top_c + low_c) / 2, y_from + 58,
                     low_c, y - 3, VDARK, 1.8)
    b += text((top_c + low_c) / 2, y_from + 22,
              "The top 4 bits end up at the bottom", 10.5, VDARK, "middle")

    # Same trick as above: the last 4 cells are too narrow to label in place
    lc = bx(1) + bw
    b += line(lc, y + BAR_H, lc, y + BAR_H + 8, MID, HAIR)
    b += line(bx(16), y + BAR_H + 8, lc, y + BAR_H + 8, MID, HAIR)
    b += text(bx(16) - 5, y + BAR_H + 12,
              "bits 3..0 are the old 63..60, and 1..0 are now the tag",
              10.0, MID, "end")

    y += BAR_H + 12 + 18

    b += note(y + 8, "Nothing is destroyed, so the mapping is exact and "
                     "decoding is a rotate and a subtract.")
    b += note(y + 24, "The doubles whose exponent bits do not land on 10 are "
                      "the only ones that get boxed:")
    b += note(y + 40, "magnitudes from 3.4e38 to 5.3e269, and from 1.9e-270 "
                      "to 2.9e-39. Everything else")
    b += note(y + 56, "stays inline: the normal float32 range, +-0.0, "
                      "double subnormals, +-inf and every NaN.")
    h = round(y + 56 + 5 + MARGIN)

    open(os.path.join(HERE, "flonum.svg"), "w").write(svg(W, h, b))
    print(f"flonum.svg: {W}x{h}")


# ------------------------------------------------------------- cover.png

def cover():
    """The social card, which is also the in post cover image.

    Two jobs, two sizes. On a timeline it is seen at about 1200px wide. In
    the post itself style.css floats it at max-width 280px, so everything
    here is sized for the timeline and then checked at the thumbnail: the
    headline survives the shrink, and what carries it below that size is the
    four coloured tag blocks running down the right hand edge.

    It is dark on purpose. Every other figure in the post is light, because
    they sit in the text column, but this one sits in someone else's
    timeline and has to win against whatever is around it.

    Authored in a 1200x630 space and rasterised at 2x for retina.
    """
    CW, CH = 1200, 630

    # A dark palette of its own. The four accents are the same four types
    # the figures colour code, brightened to hold up on a dark ground
    BG_D, FG_D = "#0b0e14", "#e6edf3"
    DIM_D, RULE_D, PANEL = "#8b949e", "#30363d", "#161b22"
    G_D, B_D, A_D, V_D = "#39e97b", "#4fc9ff", "#ffc233", "#c99cff"

    # sips rasterises this file, and it only resolves a bare font name: give
    # it a quoted comma separated stack like the figures use and it silently
    # falls back to a default sans. Monospace throughout, since the whole
    # card is about the layout of a machine word.
    MONO = "Menlo"
    ADV = 0.6022

    def ctext(x, y, s, size, fill=FG_D, anchor="start", weight=None):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" '
                f'font-size="{size}" fill="{fill}" text-anchor="{anchor}"'
                + (f' font-weight="{weight}"' if weight else "")
                + f'>{esc(s)}</text>\n')

    def cwidth(s, size):
        return len(s) * size * ADV

    M = 60
    b = rect(0, 0, CW, CH, BG_D)

    # A stripe of the four tag colours across the top, so the colour code is
    # established before the rows start using it
    seg = CW / 4.0
    for i, col in enumerate([G_D, B_D, A_D, V_D]):
        b += rect(i * seg, 0, seg + 1, 9, col)

    HEAD = 46
    l1 = "I shrank values from 16 bytes to 8"
    l2 = "and the interpreter is now 17% faster"
    for ln in (l1, l2):
        assert cwidth(ln, HEAD) <= CW - 2 * M, f"headline too wide: {ln}"
    b += ctext(M, 118, l1, HEAD, FG_D, weight="bold")
    b += ctext(M, 180, l2, HEAD, G_D, weight="bold")

    # The four cases, each one a word with its tag on the end
    rows = [
        ("fixnum",    "62-bit signed integer, stored as n << 2", "00",  G_D),
        ("pointer",   "heap block pointer",                      "001", B_D),
        ("immediate", "payload plus a 5-bit subtag",             "101", A_D),
        ("flonum",    "rotl(bits + BIAS, 4)",                    "10",  V_D),
    ]

    LAB, CAP, TAGS = 25, 27, 27
    ROW_H, GAP = 62.0, 16.0
    lab_w = max(cwidth(n, LAB) for n, _, _, _ in rows)
    x0 = M + lab_w + 22
    x1 = CW - M
    TAG_W = 96.0

    b += ctext(x0, 222, "63", 15, DIM_D)
    b += ctext(x1, 222, "0", 15, DIM_D, "end")

    y = 236.0
    for name, cap, tag, col in rows:
        b += rect(x0, y, x1 - x0 - TAG_W, ROW_H, PANEL, RULE_D, 1.4)
        b += rect(x1 - TAG_W, y, TAG_W, ROW_H, col)
        b += ctext(M, y + ROW_H / 2 + 9, name, LAB, DIM_D)
        assert cwidth(cap, CAP) <= x1 - x0 - TAG_W - 32, f"caption too wide: {cap}"
        b += ctext(x0 + 18, y + ROW_H / 2 + 9, cap, CAP, FG_D)
        # Ranged right so bit 0 lines up on every row
        b += ctext(x1 - 24, y + ROW_H / 2 + 9, tag, TAGS, BG_D,
                   "end", weight="bold")
        y += ROW_H + GAP

    y -= GAP
    y += 22
    b += line(M, y, CW - M, y, RULE_D, 1.4)
    b += ctext(M, y + 38, "github.com/maximecb/plush", 18, DIM_D)
    b += ctext(CW - M, y + 38, "pointersgonewild.com", 18, DIM_D, "end")
    assert y + 38 + 14 <= CH, "the footer runs off the bottom"
    assert CH - (y + 38) < 60, "too much dead space under the footer"

    # svg() paints a white page rect; the dark one above covers it
    body = svg(CW, CH, b, cap=False)
    body = body.replace(f'width="{CW}" height="{CH}" viewBox',
                        f'width="{CW * 2}" height="{CH * 2}" viewBox', 1)
    open(os.path.join(HERE, "cover.svg"), "w").write(body)
    print(f"cover.svg: {CW * 2}x{CH * 2}")


if __name__ == "__main__":
    value_repr()
    flonum()
    cover()
    if os.path.exists(os.path.join(HERE, "results.json")):
        charts()
    else:
        print("no results.json, skipping the charts")

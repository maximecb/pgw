#!/usr/bin/env python3
"""Generate the SVG figures for this post. Writes them next to this file.

  actors.svg         two actors, their allocators, and a message crossing
  forwarding.svg     the side table the first GC used, against the forwarding
                     pointers the rewrite uses
  address-space.svg  growing a Vec against growing a reserved range

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
  - the text column is 772px: an 820px container, less its 1rem padding, less
    the 0.5rem padding on .contents. Figures are given that whole column, so
    W below is the width one is actually seen at and the drawings are not
    scaled at all. Sizes here are real pixels, which is why a label at 11.5
    can be trusted to stay readable
  - capped at 500px tall. A figure taller than that is scaled down to fit,
    which costs it width as well, so HEIGHT_CAP below is checked, not trusted
  - on mobile the figure is stretched to the full text column, so it does get
    scaled there, but only up
  - no em dashes, en dashes or ellipses anywhere that reaches the HTML,
    since publish.sh rejects them

Sentences are capitalised. The lowercase text is labels: the names of the two
heaps, and scan and next, which are variables in gc.rs.

The palette is louder than the greys plus #a00 used elsewhere on the site.
Colour carries meaning in all three figures, so it has to survive being read
quickly: RED is the copy that has to read out of a live heap and the
bookkeeping that cost, GREEN is what replaced it and the message being
followed, BLUE is memory that has been committed or copied into.
"""

import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

FONT = "'DejaVu Sans Mono','Lucida Console',Menlo,Consolas,monospace"

INK, SUB, MID, LINE, BG = "#111", "#444", "#777", "#bbb", "#fff"
RED, GREEN, BLUE = "#cc2222", "#0e8a52", "#1560c0"
GDARK = "#0a6b40"     # outline for a green fill
DEEP = "#0f4b96"      # header cell of a block in the to-space
PALE, PALE_HDR = "#cfe0f5", "#9dc0ea"   # copied, not yet scanned
SHELL, SHELL_HDR = "#eef1f5", "#dde3ea"  # a block in the from-space
EMPTY = "#f7f9fb"     # a table slot holding nothing

HAIR, STROKE = 1.2, 1.6

W = 772          # the text column, so the drawings render 1:1
MARGIN = 14
HEIGHT_CAP = 500

# DejaVu Sans Mono advance width, in em. Used to reserve room for the row
# labels, which hang off the left of every figure. Every fallback in FONT is
# this wide or narrower, so a wrong guess costs a little whitespace rather
# than a clipped glyph.
MONO_ADV = 0.6022

LAB_SIZE = 11.5   # row labels
LAB_GAP = 10      # between a row label and the row it names


def text_width(s, size):
    return len(s) * size * MONO_ADV


def left_edge(labels):
    """Where rows start, given the labels that sit to their left."""
    return MARGIN + max(text_width(s, LAB_SIZE) for s in labels) + LAB_GAP


def svg(w, h, body, defs=""):
    assert h <= HEIGHT_CAP, f"{h}px tall, over the {HEIGHT_CAP}px cap"
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


def arrow(x1, y1, x2, y2, stroke=MID, sw=1.5, head=9):
    """Line from one point to another, with the head at the far end."""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    bx, by = x2 - ux * head, y2 - uy * head       # where the head starts
    px, py = -uy * head * 0.42, ux * head * 0.42  # across it
    return (line(x1, y1, bx, by, stroke, sw) +
            f'<path d="M {bx + px:.1f} {by + py:.1f} L {x2:.1f} {y2:.1f} '
            f'L {bx - px:.1f} {by - py:.1f} Z" fill="{stroke}"/>\n')


def row_label(x, y, h, s):
    """Name a row, right up against its left edge and centred on it."""
    return text(x - LAB_GAP, y + h / 2 + 4, s, LAB_SIZE, MID, "end")


def heading(y, s):
    assert text_width(s, 13) <= W - 2 * MARGIN, f"heading too wide: {s}"
    return text(MARGIN, y, s, 13, INK, weight="bold")


def note(y, s):
    assert text_width(s, 11.5) <= W - 2 * MARGIN, f"note too wide: {s}"
    return text(MARGIN, y, s, 11.5, SUB)


def curve_arrow(x1, y1, cx, cy, x2, y2, stroke=MID, sw=2.0, head=10):
    """Quadratic from one point to another, with the head at the far end."""
    dx, dy = x2 - cx, y2 - cy                     # tangent where it arrives
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    bx, by = x2 - ux * head, y2 - uy * head
    px, py = -uy * head * 0.42, ux * head * 0.42
    return (f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {bx:.1f} {by:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="{sw}"/>\n'
            f'<path d="M {bx + px:.1f} {by + py:.1f} L {x2:.1f} {y2:.1f} '
            f'L {bx - px:.1f} {by - py:.1f} Z" fill="{stroke}"/>\n')


def cubic_at(p0, c1, c2, p3, t):
    u = 1 - t
    return tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d
                 for a, b, c, d in zip(p0, c1, c2, p3))


def cubic_clears(p0, c1, c2, p3, box):
    """Whether a curve stays out of a rectangle, its landing aside.

    The one long curve in these figures threads a gap between two bars that
    is only as wide as the cells drawn around it. Checking it here means a
    change to those cells fails loudly rather than quietly drawing a line
    across a bar it was routed to avoid.
    """
    x0, y0, x1, y1 = box
    for i in range(1, 97):
        x, y = cubic_at(p0, c1, c2, p3, i / 100)
        if x0 <= x <= x1 and y0 <= y <= y1:
            return False
    return True


def cubic_arrow(p0, c1, c2, p3, stroke=MID, sw=2.0, head=10):
    dx, dy = p3[0] - c2[0], p3[1] - c2[1]         # tangent where it arrives
    d = math.hypot(dx, dy) or 1
    ux, uy = dx / d, dy / d
    bx, by = p3[0] - ux * head, p3[1] - uy * head
    px, py = -uy * head * 0.42, ux * head * 0.42
    return (f'<path d="M {p0[0]:.1f} {p0[1]:.1f} C {c1[0]:.1f} {c1[1]:.1f} '
            f'{c2[0]:.1f} {c2[1]:.1f} {bx:.1f} {by:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="{sw}"/>\n'
            f'<path d="M {bx + px:.1f} {by + py:.1f} L {p3[0]:.1f} {p3[1]:.1f} '
            f'L {bx - px:.1f} {by - py:.1f} Z" fill="{stroke}"/>\n')


def badge(x, y, n, fill):
    """Numbered step marker, drawn rather than written, so that the figure
    needs no character outside the set publish.sh allows."""
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="9.5" fill="{fill}"/>\n' +
            text(x, y + 4.5, str(n), 12, BG, "middle", weight="bold"))


def caret(x, y, label, anchor="middle", fill=INK):
    """Marker under a bar, pointing up at the byte it names.

    A caret on the last byte of a heap sits on the right margin, where a
    centred label would run off the canvas, so the anchor is a parameter.
    """
    lx = x if anchor == "middle" else x - 1
    return (f'<path d="M {x:.1f} {y:.1f} L {x - 5.5:.1f} {y + 10:.1f} '
            f'L {x + 5.5:.1f} {y + 10:.1f} Z" fill="{fill}"/>\n' +
            text(lx, y + 24, label, 11.5, fill, anchor))


# ---------------------------------------------------------------- figure 1
# What vm.rs actually does, so the drawing does not invent a mechanism:
# an actor owns a private Alloc that only its own thread ever touches, and a
# msg_alloc behind a Mutex that senders write into. send() locks the
# receiver's msg_alloc, copies the graph out of its own live heap with an undo
# log, and queues the message while still holding that lock. take_msg() then
# copies the message out of the buffer and into the private heap on receipt,
# and the buffer is reset once the queue drains.
BOX_W, BOX_PAD, ABAR_H = 336, 12, 40
BOX_Y = 40

# Cells drawn in each allocator, filled from the left like the bump allocator
# each of them is. Green is the message being followed across the figure.
CELLS = {
    "a_msg":  [(52, BLUE, DEEP)],
    "a_heap": [(39, SHELL, MID)] * 4 + [(39, GREEN, GDARK)] * 2,
    "b_msg":  [(48, BLUE, DEEP)] * 3 + [(39, GREEN, GDARK)] * 2,
    "b_heap": [(39, SHELL, MID)] * 4 + [(39, GREEN, GDARK)] * 2,
}


def green_span(x, cells):
    """Where the message sits in a bar. It is drawn the same width in all
    three, since a copy of it is never larger than the thing it copied."""
    assert all(c[1] == GREEN for c in cells[-2:]), "green is the last run"
    lo = x + sum(c[0] for c in cells if c[1] != GREEN)
    return lo, lo + sum(c[0] for c in cells if c[1] == GREEN)


def alloc_bar(x, y, w, label, cells):
    # Only the left-hand actor is labelled. Both boxes hold the same two
    # allocators at the same heights, so the labels read across, and leaving
    # the right-hand one clear is what lets the send arrive on the message
    # from above instead of crossing the queue already sitting in the buffer.
    b = text(x, y - 6, label, 10.5, MID) if label else ""
    b += rect(x, y, w, ABAR_H, EMPTY, LINE, HAIR, 3)
    cx = x
    for cw, fill, stroke in cells:
        b += rect(cx, y, cw, ABAR_H, fill, stroke, HAIR)
        cx += cw
    return b + rect(x, y, w, ABAR_H, "none", LINE, HAIR, 3)


def fig_actors():
    inner_w = BOX_W - 2 * BOX_PAD
    ax, bx = MARGIN, W - MARGIN - BOX_W
    ain, bin_ = ax + BOX_PAD, bx + BOX_PAD
    msg_y, heap_y = BOX_Y + 52, BOX_Y + 140
    box_h = 196

    b = heading(20, "Each actor owns two allocators, and a message is copied "
                    "across the boundary")

    for x, inner, name in ((ax, ain, "Actor A"), (bx, bin_, "Actor B")):
        b += rect(x, BOX_Y, BOX_W, box_h, BG, MID, STROKE, 6)
        b += text(inner, BOX_Y + 22, name, 13, INK, weight="bold")

    b += alloc_bar(ain, msg_y, inner_w,
                   "message allocator, locked while written", CELLS["a_msg"])
    b += alloc_bar(ain, heap_y, inner_w,
                   "private heap, never locked", CELLS["a_heap"])
    b += alloc_bar(bin_, msg_y, inner_w, None, CELLS["b_msg"])
    b += alloc_bar(bin_, heap_y, inner_w, None, CELLS["b_heap"])

    def mid(span):
        return (span[0] + span[1]) / 2

    a_msg = green_span(ain, CELLS["a_heap"])
    b_buf = green_span(bin_, CELLS["b_msg"])
    b_own = green_span(bin_, CELLS["b_heap"])

    # Out of the top of the message in A's heap and down onto the copy of it
    # in B's buffer. The first control point holds the curve flat and low
    # until it is past A's own buffer, which sits directly above where it
    # starts; the second lifts it over B's buffer so that it comes down on
    # the message rather than crossing the queue in front of it.
    send = ((mid(a_msg), heap_y),
            (ax + BOX_W + 10, heap_y - 2),
            (bx + 8, 10),
            (mid(b_buf), msg_y))
    for bar in (ain, bin_):
        assert cubic_clears(*send, (bar, msg_y, bar + inner_w, msg_y + ABAR_H)), \
            "the send crosses a buffer it was routed around"
    b += cubic_arrow(*send, RED, 2.2)
    b += badge((ax + BOX_W + bx) / 2, 140, 1, RED)

    b += arrow(mid(b_buf), msg_y + ABAR_H, mid(b_own), heap_y, BLUE, 2.2, 10)
    b += badge(b_own[1] - 18, msg_y + ABAR_H + 20, 2, BLUE)

    y = BOX_Y + box_h + 34
    b += badge(MARGIN + 9, y - 4, 1, RED)
    b += text(MARGIN + 26, y, "The sender writes into the receiver's buffer, "
              "reading out of a heap that has to stay live", 11.5, SUB)

    y += 26
    b += badge(MARGIN + 9, y - 4, 2, BLUE)
    b += text(MARGIN + 26, y, "The receiver copies the message into its own "
              "heap, and the buffer is reset once the queue drains", 11.5, SUB)

    return svg(W, int(y + MARGIN), b)


# ---------------------------------------------------------------- figure 2
NB = 8            # blocks drawn in each heap
LETTERS = "ABCDEFGH"
SLOTS = 20        # slots in the side table
SCANNED = 3       # to-space blocks the scan pointer has passed

# Which slot each block hashes to. The order has nothing to do with the order
# of either heap, which is the whole point of the drawing. Written out rather
# than generated so the figure does not move around between runs.
SLOT_OF = [13, 2, 17, 6, 9, 0, 15, 4]
assert len(SLOT_OF) == NB and len(set(SLOT_OF)) == NB and max(SLOT_OF) < SLOTS

HDR_W = 20        # the header cell at the front of every block
BAR_H = 34


def blocks(x0, y, pitch, fills, hdrs, inks, h=BAR_H):
    """A run of contiguous heap blocks, each with its header cell in front.

    Contiguous on purpose: these heaps are bump allocated, so a gap between
    blocks would be a lie about how they are laid out.
    """
    b = ""
    for i in range(NB):
        x = x0 + i * pitch
        b += rect(x, y, pitch, h, fills[i])
        b += rect(x, y, HDR_W, h, hdrs[i])
        b += rect(x, y, pitch, h, "none", MID, HAIR)
        b += line(x + HDR_W, y, x + HDR_W, y + h, MID, HAIR)
        b += text(x + HDR_W + (pitch - HDR_W) / 2, y + h / 2 + 5,
                  LETTERS[i], 14, inks[i], "middle", weight="bold")
    return b


def fig_forwarding():
    gx = left_edge(["from", "table", "to"])
    avail = W - MARGIN - gx
    pitch, slot = avail / NB, avail / SLOTS

    b = ""

    # --- the side table -------------------------------------------------
    b += heading(20, "A side table from each block to its copy")

    fy, ty, oy = 36, 106, 176
    b += row_label(gx, fy, BAR_H, "from")
    b += blocks(gx, fy, pitch, [SHELL] * NB, [SHELL_HDR] * NB, [INK] * NB)

    # Each slot is a pair of cells, a key and a value, because that is what an
    # entry costs. Two of them per live object is the size complaint, drawn.
    b += row_label(gx, ty, BAR_H, "table")
    for s in range(SLOTS):
        x = gx + s * slot
        held = SLOT_OF.index(s) if s in SLOT_OF else None
        b += rect(x, ty, slot / 2, BAR_H, RED if held is not None else EMPTY)
        b += rect(x + slot / 2, ty, slot / 2, BAR_H,
                  PALE if held is not None else EMPTY)
        if held is not None:
            b += text(x + slot / 4, ty + BAR_H / 2 + 5, LETTERS[held], 12,
                      BG, "middle", weight="bold")
        b += rect(x, ty, slot, BAR_H, "none", LINE, HAIR)
        b += line(x + slot / 2, ty, x + slot / 2, ty + BAR_H, LINE, HAIR)

    b += row_label(gx, oy, BAR_H, "to")
    b += blocks(gx, oy, pitch, [BLUE] * NB, [DEEP] * NB, [BG] * NB)

    # The forwarding of a block leaves from the middle of its header, the same
    # place it leaves from in the panel below, and lands just past the header
    # of the copy, which is the address a pointer to it holds. Only the route
    # between those two points differs between the panels, which is the point.
    # The key cell of a slot holds the from-space address and the value cell
    # holds the to-space one, so each arrow meets the half that holds it.
    for i, s in enumerate(SLOT_OF):
        x = gx + i * pitch
        sx = gx + s * slot
        b += arrow(x + HDR_W / 2, fy + BAR_H, sx + slot / 4, ty, RED, 1.4, 8)
        b += arrow(sx + 3 * slot / 4, ty + BAR_H, x + HDR_W, oy, RED, 1.4, 8)

    b += note(oy + BAR_H + 24,
              "20 slots of two pointers to track 8 small nodes, and every "
              "lookup lands at an unpredictable address")

    div = oy + BAR_H + 42
    b += line(MARGIN, div, W - MARGIN, div, LINE, HAIR)

    # --- forwarding pointers --------------------------------------------
    b += heading(div + 26, "A forwarding address, written into the header of "
                           "the block itself")

    fy2, oy2 = div + 42, div + 124
    b += row_label(gx, fy2, BAR_H, "from")
    b += blocks(gx, fy2, pitch, [SHELL] * NB, [GREEN] * NB, [INK] * NB)

    b += row_label(gx, oy2, BAR_H, "to")
    b += blocks(gx, oy2, pitch,
                [BLUE if i < SCANNED else PALE for i in range(NB)],
                [DEEP if i < SCANNED else PALE_HDR for i in range(NB)],
                [BG if i < SCANNED else INK for i in range(NB)])

    # Out of the header cell, where the address is written, and down onto the
    # address it holds: the same eight arrows as above, with nothing in
    # between to route them through
    for i in range(NB):
        x = gx + i * pitch
        b += arrow(x + HDR_W / 2, fy2 + BAR_H, x + HDR_W, oy2, GREEN, 2.0, 9)

    b += caret(gx + SCANNED * pitch, oy2 + BAR_H + 4, "scan")
    b += caret(gx + NB * pitch, oy2 + BAR_H + 4, "next", "end")

    h = oy2 + BAR_H + 4 + 24 + 22
    b += note(h, "Nothing outside the two heaps is touched, and the copy is "
                 "done once scan catches up with next")

    return svg(W, int(h + MARGIN), b)


# ---------------------------------------------------------------- figure 3
# Sizes are the ones in plush/src/alloc.rs: a message allocator starts at
# MSG_INIT_SIZE and reserves MSG_RESERVE_SIZE of address space up front.
INIT, RESERVE = "2 MB", "16 GB"
TRACK_H = 32

HATCH = ('<pattern id="reserved" width="9" height="9" '
         'patternUnits="userSpaceOnUse" patternTransform="rotate(45)">\n'
         f'<rect width="9" height="9" fill="{BG}"/>\n'
         f'<line x1="0" y1="0" x2="0" y2="9" stroke="#dbe1e8" stroke-width="3.5"/>\n'
         '</pattern>\n')


def committed(x, y, w, label):
    """A committed region, sized at its far edge rather than in the middle.

    The guide line crosses every row near its left, so a centred label would
    sit under the marker in the narrow rows.
    """
    return (rect(x, y, w, TRACK_H, BLUE, DEEP, HAIR) +
            text(x + w - 10, y + TRACK_H / 2 + 5, label, 13, BG, "end",
                 weight="bold"))


def spot(x, y, ok):
    """Where the guide line crosses a row, and whether it lands on anything."""
    c = GREEN if ok else RED
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.5" fill="{c}" '
            f'stroke="{BG}" stroke-width="1.6"/>\n')


def fig_address_space():
    gx = left_edge(["before", "grow", "shrink"])
    avail = W - MARGIN - gx
    gux = gx + 84          # the address the pointer holds, in every row

    b = ""

    # --- a Vec ----------------------------------------------------------
    b += heading(20, "A Vec that grows may move, and a pointer into it "
                     "does not follow")
    b += text(gux, 38, "A pointer into it", 11.5, SUB, "middle")

    ay, by = 54, 106
    b += line(gux, 44, gux, by + TRACK_H + 6, MID, HAIR, "3 3")

    for y in (ay, by):
        b += rect(gx, y, avail, TRACK_H, "none", LINE, HAIR, 3)

    b += row_label(gx, ay, TRACK_H, "before")
    b += committed(gx, ay, 140, INIT)
    b += spot(gux, ay + TRACK_H / 2, True)

    b += row_label(gx, by, TRACK_H, "grow")
    b += rect(gx, by, 140, TRACK_H, BG, RED, HAIR)
    b += line(gx, by, gx + 140, by + TRACK_H, RED, HAIR)
    b += line(gx, by + TRACK_H, gx + 140, by, RED, HAIR)
    b += committed(W - MARGIN - 280, by, 280, "4 MB")
    b += spot(gux, by + TRACK_H / 2, False)
    b += text(gx + 140 + (W - MARGIN - 280 - gx - 140) / 2, by + TRACK_H / 2 + 4,
              "Some other address", 11, MID, "middle")

    b += note(by + TRACK_H + 28,
              "The bytes are somewhere else now, so the address that was "
              "handed out points at nothing")

    div = by + TRACK_H + 46
    b += line(MARGIN, div, W - MARGIN, div, LINE, HAIR)

    # --- a reserved range -----------------------------------------------
    b += heading(div + 26, "A reserved range grows in place, and every "
                           "address in it keeps its meaning")
    b += text(gux, div + 44, "The same pointer", 11.5, SUB, "middle")

    rows = [("before", 140, INIT), ("grow", 420, "16 MB"), ("shrink", 224, "4 MB")]
    top = div + 50
    b += line(gux, top - 4, gux, top + 3 * 48 - 16 + 6, MID, HAIR, "3 3")

    for i, (lab, w, size) in enumerate(rows):
        y = top + i * 48
        b += rect(gx, y, avail, TRACK_H, "url(#reserved)", MID, HAIR, 3)
        b += row_label(gx, y, TRACK_H, lab)
        b += committed(gx, y, w, size)
        b += spot(gux, y + TRACK_H / 2, True)

    # The reservation is one range across all three rows, so it is named once,
    # under the stack rather than beside any single row
    ry = top + 3 * 48 - 16 + 12
    b += line(gx, ry, W - MARGIN, ry, MID, STROKE)
    b += line(gx, ry - 5, gx, ry + 5, MID, STROKE)
    b += line(W - MARGIN, ry - 5, W - MARGIN, ry + 5, MID, STROKE)
    b += text((gx + W - MARGIN) / 2, ry + 19,
              f"{RESERVE} of address space, PROT_NONE, with no RAM behind it",
              12, SUB, "middle")

    # Not "mprotect commits ...", which would put a syscall at the front of a
    # sentence and make it the one thing that cannot be capitalised
    h = ry + 19 + 22
    b += note(h, "Pages are committed and released in place with mprotect, "
                 "so queued messages stay put")

    return svg(W, int(h + MARGIN), b, HATCH)


FIGURES = [("actors.svg", fig_actors),
           ("forwarding.svg", fig_forwarding),
           ("address-space.svg", fig_address_space)]

# Characters publish.sh refuses to ship, checked here rather than found later
REJECTED = ("—", "–", "…", "“", "”", "‘", "’")

if __name__ == "__main__":
    for name, fn in FIGURES:
        data = fn()
        for bad in REJECTED:
            assert bad not in data, f"{name} contains a rejected character"
        with open(os.path.join(HERE, name), "w") as f:
            f.write(data)
        print(f"{name:20} {len(data):6} bytes")

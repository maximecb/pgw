#!/usr/bin/env python3
"""Generate the SVG figures for this post. Writes them next to this file.

  interp-speedup.svg   the three Plush builds, old normalized to 1.0x
  langs.svg            Plush against Lua, CRuby and CPython, CPython at 1.0x

Both read the raw timing data copied in next to this file, and take the median
of the 11 runs the same way analyze.py does, so the figures cannot drift from
the tables in the post.

Vertical bars here, not the horizontal ones of the last post. These are grouped
comparisons: several series measured on the same benchmark. Grouping reads far
better side by side than stacked in rows, and a baseline at 1.0x is a floor to
stand on rather than a line to cross.

NO PADDING AROUND THE DRAWINGS. The browser scales the whole canvas to fit the
text column, so every blank pixel inside the canvas is a pixel the drawing does
not get. See the last post's gen_svgs.py for the long version. In short: a
figure's height is whatever its last element reaches, plus MARGIN, and ink runs
out to MARGIN on the left and the right.

Drawing constraints come from site/style.css:
  - light only, white background, DejaVu Sans Mono
  - the text column is 772px, so the figures render 1:1 and are not scaled
  - capped at 500px tall, so HEIGHT_CAP below is checked, not trusted
  - no em dashes, en dashes or ellipses anywhere that reaches the HTML,
    since publish.sh rejects them

Colour is the build or the runtime, and it means the same thing in both
figures: GREY is the baseline being measured against, BLUE is a middle step,
GREEN is the interpreter this post is about. RED is only ever a runtime that
came out slower than the baseline.
"""

import math
import os
import re
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))

FONT = "'DejaVu Sans Mono','Lucida Console',Menlo,Consolas,monospace"

INK, SUB, MID, LINE, BG = "#111", "#444", "#777", "#c9c9c9", "#fff"

# Fill then edge. Both figures ramp cool to warm as the interpreter gets
# faster, so the temperature of a bar is its speed before any number is read.
# The two ends mean the same thing in both: COOL is the baseline, HOT is the
# new Plush. PLUM only fills the extra step the second figure needs.
#
# The last post's formula: a tinted fill outlined in the same hue at full
# strength. Fills sit near 38% of the way from white to the hue, against the
# 17% of memory.svg, which was too washed out at these widths. Every hue is
# held at about the same lightness so no step reads heavier than its
# neighbours. COOL, AMBER and HOT are the three Plush builds, and mean the
# same build in both figures; MOSS, ORCHID and SLATE name the other three
# runtimes in the second figure.
SLATE, SLATE_D = "#c1c5c9", "#5b6672"
ORCHID, ORCHID_D = "#cfaee5", "#6b3fa0"
MOSS, MOSS_D = "#a6dcc5", "#0a6b40"
COOL, COOL_D = "#a8c5ee", "#2a5db0"
AMBER, AMBER_D = "#f5ca6d", "#a87908"
HOT, HOT_D = "#f5a589", "#c2451f"

HAIR, STROKE = 1.2, 1.6

W = 772
MARGIN = 14
HEIGHT_CAP = 500

MONO_ADV = 0.6022


def text_width(s, size):
    return len(s) * size * MONO_ADV


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg(w, h, body, cap=True):
    assert not cap or h <= HEIGHT_CAP, f"{h}px tall, over the {HEIGHT_CAP}px cap"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">\n'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>\n' + body + '</svg>\n')


def text(x, y, s, size=13, fill=INK, anchor="start", weight=None, rot=None,
         preserve=False):
    t = (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
         f'fill="{fill}" text-anchor="{anchor}"')
    if weight:
        t += f' font-weight="{weight}"'
    if rot is not None:
        t += f' transform="rotate({rot} {x:.1f} {y:.1f})"'
    # Leading spaces are collapsed otherwise, which flattens indented source
    if preserve:
        t += ' xml:space="preserve"'
    return t + f'>{esc(s)}</text>\n'


def rect(x, y, w, h, fill, stroke=None, sw=HAIR):
    s = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}"'
    return s + '/>\n'


def line(x1, y1, x2, y2, stroke=MID, sw=HAIR, dash=None):
    s = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
         f'stroke="{stroke}" stroke-width="{sw}"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s + '/>\n'


def note(y, s, x=MARGIN, size=11.0, fill=SUB):
    assert x + text_width(s, size) <= W - MARGIN, f"note too wide: {s}"
    return text(x, y, s, size, fill)


LEG_ROW = 16.0


def legend(y, x, entries, size=11.0, swatch=10.0, gap=22.0, sw=HAIR):
    """Swatches and names from x, wrapping. Returns the svg and its rows."""
    s, cx, rows = "", x, 1
    for name, fill, edge in entries:
        w = swatch + 5 + text_width(name, size)
        assert x + w <= W - MARGIN, f"legend entry too wide: {name}"
        if cx > x and cx + w > W - MARGIN:
            cx, rows = x, rows + 1
            y += LEG_ROW
        s += rect(cx, y - swatch + 1, swatch, swatch, fill, edge, sw)
        s += text(cx + swatch + 5, y, name, size, SUB)
        cx += w + gap
    return s, rows


# ------------------------------------------------------------------ data

def parse(path):
    """The subset of YAML run_bench.py emits: one nesting level under results."""
    results, section, bench = {}, None, None
    for raw in open(path):
        ln = raw.rstrip("\n")
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if not ln.startswith(" "):
            section = ln.rstrip(":")
            continue
        if section != "results":
            continue
        if len(ln) - len(ln.lstrip()) == 2:
            bench = ln.strip().rstrip(":")
            results[bench] = {}
        else:
            runner, _, vals = ln.strip().partition(": ")
            results[bench][runner] = [float(n) for n in re.findall(r"[\d.]+", vals)]
    return results


def geomean(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


# -------------------------------------------------- grouped vertical bars

def grouped_bars(fname, sub, groups, series, notes,
                 plot_h, bar_w, bar_gap, group_gap, label_rot,
                 refline=None, value_labels=False, step=0.5,
                 sep_before=None, bold_labels=(), bar_sw=HAIR):
    """One cluster of bars per group, sharing a zero based y axis.

    groups is a list of (label, [value per series]); series is a list of
    (name, fill, edge). Bars start at zero, so a bar's height is the ratio it
    stands for and two bars can be compared by eye without reading a number.
    """
    fmt = lambda v: f"{v:.2f}x"

    hi = max(max(vs) for _, vs in groups) * 1.06
    ticks = [t / 100.0 for t in range(0, int(hi * 100) + 1, int(step * 100))]
    tick_w = max(text_width(fmt(t), 10.0) for t in ticks)

    x0 = MARGIN + tick_w + 7
    x1 = W - MARGIN

    # No title inside the canvas: the markdown caption already names the
    # figure on the page, and repeating it wastes vertical space
    y = MARGIN + 11
    b = ""
    for i, ln in enumerate([sub] if isinstance(sub, str) else sub):
        if i:
            y += 16
        b += note(y, ln)
    y += 20
    leg, leg_rows = legend(y, x0, series, sw=bar_sw)
    b += leg
    y += (leg_rows - 1) * LEG_ROW

    top = y + 12
    bot = top + plot_h

    def sy(v):
        return bot - plot_h * v / hi

    for t in ticks:
        # The reference line, drawn last over the bars, replaces its gridline
        if refline is None or abs(t - refline) > 1e-9:
            b += line(x0, sy(t), x1, sy(t), LINE, HAIR, None if t == 0 else "3 3")
        b += text(x0 - 7, sy(t) + 3.5, fmt(t), 10.0, MID, "end")

    group_w = len(series) * bar_w + (len(series) - 1) * bar_gap
    span = len(groups) * group_w + (len(groups) - 1) * group_gap
    assert span <= x1 - x0, f"{fname}: bars need {span:.0f}px, have {x1 - x0:.0f}"
    gx = x0 + (x1 - x0 - span) / 2

    vlabels = ""
    for gi, (glab, vals) in enumerate(groups):
        if gi == sep_before:
            b += line(gx - group_gap / 2, top - 4, gx - group_gap / 2, bot + 4,
                      MID, HAIR)
        for si, v in enumerate(vals):
            _, fill, edge = series[si]
            x = gx + si * (bar_w + bar_gap)
            b += rect(x, sy(v), bar_w, bot - sy(v), fill, edge, bar_sw)
            if value_labels:
                vlabels += text(x + bar_w / 2, sy(v) - 6, fmt(v), 11.0, edge,
                                "middle", weight="bold")
        cx = gx + group_w / 2
        wt = "bold" if glab in bold_labels else None
        if label_rot:
            # rotate(-90) turns the glyph stack to the left of its baseline,
            # so nudge the anchor right to sit the body over the group centre
            b += text(cx + 0.25 * 10.5, bot + 6, glab, 10.5, INK, "end",
                      weight=wt, rot=-90)
        else:
            b += text(cx, bot + 16, glab, 11.5, INK, "middle", weight=wt)
        gx += group_w + group_gap

    if refline is not None:
        b += line(x0, sy(refline), x1, sy(refline), INK, STROKE, "5 4")
    b += vlabels

    if label_rot:
        y = bot + 6 + max(text_width(g[0], 10.5) for g in groups) + 6
    else:
        y = bot + 16 + 14
    for ln in notes:
        y += 15
        b += note(y, ln)

    h = round(y + 5 + MARGIN)
    open(os.path.join(HERE, fname), "w").write(svg(W, h, b))
    print(f"{fname}: {W}x{h}")


# ------------------------------------------------------ interp-speedup.svg

def interp_speedup():
    """The three builds, per benchmark, as a multiple of the old VM's speed."""
    res = parse(os.path.join(HERE, "raw_data.yaml"))
    med = {b: {k: statistics.median(v) for k, v in r.items()}
           for b, r in res.items() if b != "startup"}

    # Slowest to fastest, so the chart climbs left to right into the geomean
    rows = sorted(((b, [1.0, m["old"] / m["mid"], m["old"] / m["new"]])
                   for b, m in med.items()),
                  key=lambda r: r[1][2])
    gm = [1.0,
          geomean([r[1][1] for r in rows]),
          geomean([r[1][2] for r in rows])]
    rows.append(("geomean", gm))

    grouped_bars(
        "interp-speedup.svg",
        ["Median of 11 interleaved runs on Apple M5 Silicon. Higher is better.",
         "Values are normalized with the old VM at 1.00x."],
        rows,
        [("Stack-based interpreter", COOL, COOL_D),
         ("Register-based interpreter", AMBER, AMBER_D),
         ("Register-based + optimizations", HOT, HOT_D)],
        [f"Geometric mean over the {len(rows) - 1} benchmarks: "
         f"{gm[1]:.2f}x for the rewrite alone, {gm[2]:.2f}x with the "
         f"optimizations on top.",
         "The four gc_* benchmarks are flat because the collector was not "
         "touched."],
        # Heavier outlines than the second figure: at 8px the bars are mostly
        # surrounded by white, so the same fill reads paler than it does there
        plot_h=232, bar_w=8.0, bar_gap=0.0, group_gap=4.4, label_rot=True,
        sep_before=len(rows) - 1, bold_labels=("geomean",), bar_sw=1.6)


# ---------------------------------------------------------------- langs.svg

def langs():
    """Plush against the three other interpreters, CPython as the baseline."""
    res = parse(os.path.join(HERE, "raw_langs.yaml"))
    med = {b: {k: statistics.median(v) for k, v in r.items()}
           for b, r in res.items() if b != "startup"}

    # The other runtimes first, then the three Plush builds on the right in
    # the order they were written, so the trio reads as its own progression
    order = [("CPython", "python"), ("CRuby", "ruby"), ("Lua", "lua"),
             ("Plush old", "plush_old"), ("Plush mid", "plush_mid"),
             ("Plush new", "plush_new")]
    groups = [(lab, [med[b]["python"] / med[b][k] for _, k in order])
              for b, lab in [("binary_tree", "binary_tree"), ("fib", "fib(38)")]]

    grouped_bars(
        "langs.svg",
        "Median of 11 interleaved runs, same machine. Higher is better. "
        "Values are normalized with CPython at 1.00x.",
        groups,
        [("CPython 3.14.6", SLATE, SLATE_D), ("CRuby 4.0.6", ORCHID, ORCHID_D),
         ("Lua 5.5.1", MOSS, MOSS_D), ("Plush stack", COOL, COOL_D),
         ("Plush register", AMBER, AMBER_D),
         ("Plush optimized", HOT, HOT_D)],
        ["Wall clock for the whole process, so interpreter startup is "
         "included: ~14ms CPython, ~24ms CRuby,",
         "~2ms Lua, ~4ms Plush. Two benchmarks that translate cleanly across "
         "four languages, not a general claim."],
        plot_h=250, bar_w=48.0, bar_gap=5.0, group_gap=50.0, label_rot=False,
        refline=1.0, value_labels=True)


# ----------------------------------------------------------- bytecode.svg

# The register listings are verbatim Function.dump_bytecode() output at
# 216fd26. The stack VM at 4637315f has no dumper, so those were read off
# its codegen.rs: parameters are Decl::Arg, hence get_arg and not get_local,
# and a jump operand is the offset from the instruction after it.
#
# The flag marks an instruction that only moves a value on or off the
# temporary stack. Those are what the register machine does not need, and
# showing which ones vanish is the whole point of the figure.
EXAMPLES = [
    (["fun expr(a, b, c)",
      "{",
      "    return a + b * c;",
      "}"],
     [("get_arg 0", "", True), ("get_arg 1", "", True),
      ("get_arg 2", "", True), ("mul", "", False),
      ("add", "", False), ("ret", "", False)],
     [("mul r3, r1, r2", "", False), ("add r3, r0, r3", "", False),
      ("ret r3", "", False)]),

    (["fun branch(a)",
      "{",
      "    if (a > 10) {",
      "        return 1;",
      "    }",
      "    return 2;",
      "}"],
     [("get_arg 0", "", True), ("push 10", "", True), ("gt", "", False),
      ("if_false 2", "-> 006", False), ("push 1", "", True),
      ("ret", "", False), ("push 2", "", True), ("ret", "", False)],
     [("jngt_imm16 r0, 10, 1", "-> 002", False), ("ret_imm40 4", "", False),
      ("ret_imm40 8", "", False)]),
]

SRC_W, COL_GAP = 196.0, 14.0
ROW_P, CODE = 15.0, 11.0


def bytecode():
    """The same two functions, compiled by each VM, side by side."""
    b = ""

    x_src = MARGIN
    x_st = x_src + SRC_W + COL_GAP
    col_w = (W - MARGIN - x_st - COL_GAP) / 2
    x_rg = x_st + col_w + COL_GAP

    def column(x, y, title, rows, colour, edge, count_y):
        s = rect(x, y, col_w, 20, colour, edge, HAIR)
        s += text(x + 7, y + 14, title, 11.0, INK)
        ry = y + 24
        # Zero based, so the indices agree with the branch targets in the
        # comments: if_false lands on 006, jngt_imm16 on 002
        tx = x + 7 + text_width("000", 9.5) + 9
        for i, (txt, cmt, dim) in enumerate(rows):
            s += text(x + 7, ry + 11, f"{i:03d}", 9.5, MID)
            s += text(tx, ry + 11, txt, CODE, MID if dim else INK)
            if cmt:
                s += text(tx + text_width(txt, CODE) + 8, ry + 11,
                          "; " + cmt, 9.5, LINE if dim else MID)
            ry += ROW_P
        # Both columns count off the taller listing, so the two totals line up
        s += text(x + 7, count_y, f"{len(rows)} instructions", 11.5, edge,
                  weight="bold")
        return s

    y = MARGIN
    for i, (src, st, rg) in enumerate(EXAMPLES):
        rows = max(len(src), len(st), len(rg))
        count_y = y + 24 + rows * ROW_P + 16
        for j, ln in enumerate(src):
            # Indent as an x offset rather than literal spaces, which some
            # renderers collapse even with xml:space set
            ind = len(ln) - len(ln.lstrip())
            b += text(x_src + ind * CODE * MONO_ADV, y + 24 + j * ROW_P + 11,
                      ln.lstrip(), CODE, INK)
        b += column(x_st, y, "Stack-based", st, COOL, COOL_D, count_y)
        b += column(x_rg, y, "Register-based", rg, HOT, HOT_D, count_y)
        y = count_y + (28 if i < len(EXAMPLES) - 1 else 0)
    y += 24
    b += note(y, "Grey instructions do nothing but move a value on or off the "
                 "temporary stack.")
    h = round(y + 5 + MARGIN)

    open(os.path.join(HERE, "bytecode.svg"), "w").write(svg(W, h, b))
    print(f"bytecode.svg: {W}x{h}")


# ---------------------------------------------------------- insn-word.svg

def insn_word():
    """One instruction word, drawn with bit 0 on the left.

    Field positions are what insns.rs actually encodes: the opcode takes
    the low 8 bits, operands pack upward from there, and the last operand
    is written at 64 - its width, so decoding it is a single shift. Lua's
    word is drawn at the same scale rather than stretched to fit, so that
    it reads as half as wide, which it is.
    """
    ROW_H = 30.0

    rows = [
        # label, bits, fields as (lo, hi, fill, edge, caption)
        # Lua 5.5 positions from lopcodes.h: OP at 0 (7 bits), A at 7, the k
        # flag at 15, B at 16, C at 24. Bx starts at 15, swallowing the flag
        # bit, which is how a wide operand is made. ADD is R[A] := R[B]+R[C],
        # all three plain registers, and it does not use k
        ("Lua ADD", 32, [
            (0, 6, HOT, HOT_D, "OP (7)"),
            (7, 14, COOL, COOL_D, "A (8)"),
            (15, 15, SLATE, SLATE_D, "k"),
            (16, 23, COOL, COOL_D, "B (8)"),
            (24, 31, COOL, COOL_D, "C (8)")]),
        ("Lua LOADK", 32, [
            (0, 6, HOT, HOT_D, "OP (7)"),
            (7, 14, COOL, COOL_D, "A (8)"),
            (15, 31, AMBER, AMBER_D, "Bx (17)")]),
        ("add", 64, [
            (0, 7, HOT, HOT_D, "opcode"),
            (8, 23, COOL, COOL_D, "dst (16)"),
            (24, 39, COOL, COOL_D, "a (16)"),
            (40, 47, SLATE, SLATE_D, "unused"),
            (48, 63, COOL, COOL_D, "b (16)")]),
        ("jlt_imm16", 64, [
            (0, 7, HOT, HOT_D, "opcode"),
            (8, 23, COOL, COOL_D, "a (16)"),
            (24, 39, AMBER, AMBER_D, "imm (16)"),
            (40, 63, AMBER, AMBER_D, "disp (24)")]),
        # Five operands in one word: two registers and three 6-bit fields,
        # with len top-aligned like every other trailing operand
        ("rshift_mask", 64, [
            (0, 7, HOT, HOT_D, "opcode"),
            (8, 23, COOL, COOL_D, "dst (16)"),
            (24, 39, COOL, COOL_D, "a (16)"),
            (40, 45, AMBER, AMBER_D, "shift (6)"),
            (46, 51, AMBER, AMBER_D, "lo (6)"),
            (52, 57, SLATE, SLATE_D, "unused"),
            (58, 63, AMBER, AMBER_D, "len (6)")]),
        ("load_imm40", 64, [
            (0, 7, HOT, HOT_D, "opcode"),
            (8, 23, COOL, COOL_D, "dst (16)"),
            (24, 63, AMBER, AMBER_D, "imm (40)")]),
    ]

    lab_w = max(text_width(r[0], 11.5) for r in rows)
    x0 = MARGIN + lab_w + 10
    bw = (W - MARGIN - x0) / 64.0

    def bx(bit):
        return x0 + bit * bw

    b = note(MARGIN + 11,
             "Bit 0 is on the left, so the opcode reads first. Lua's "
             "instruction word is drawn to the same scale.")

    top = MARGIN + 11 + 26
    for bit in [0, 8, 16, 24, 32, 40, 48, 56]:
        b += text(bx(bit), top - 6, str(bit), 9.5, SUB, "middle")
    b += text(bx(64), top - 6, "64", 9.5, SUB, "middle")

    y = top
    for i, (lab, nbits, fields) in enumerate(rows):
        for lo, hi, fill, edge, cap in fields:
            fx, fw = bx(lo), (hi - lo + 1) * bw
            b += rect(fx, y, fw, ROW_H, fill, edge, HAIR)
            assert text_width(cap, 10.0) <= fw - 4, f"{cap!r} does not fit"
            b += text(fx + fw / 2, y + ROW_H / 2 + 4, cap, 10.0, INK, "middle")
        b += text(x0 - 10, y + ROW_H / 2 + 4, lab, 11.5, INK, "end")
        if nbits < 64:
            b += line(bx(nbits), y - 4, bx(nbits), y + ROW_H + 4, MID,
                      HAIR, "3 3")
            if i == 0:
                b += text(bx(nbits) + 8, y + ROW_H / 2 + 4,
                          "Lua stops here, at 32 bits", 10.0, MID)
            # Wider gap only where the short rows give way to the 64-bit ones
            last = i + 1 < len(rows) and rows[i + 1][1] == 64
            y += ROW_H + (26 if last else 10)
        else:
            y += ROW_H + 10

    # No explanatory text: the prose around the figure carries it
    h = round(y - 10 + MARGIN)

    open(os.path.join(HERE, "insn-word.svg"), "w").write(svg(W, h, b))
    print(f"insn-word.svg: {W}x{h}")


# ------------------------------------------------------------- cover.png

def cover():
    """The social card: langs.svg, cut down to what survives a thumbnail.

    Two jobs, two sizes. On a timeline it is seen at about 1200px wide. In
    the post itself style.css floats it at max-width 280px, so the two older
    Plush builds are dropped here: twelve bars is legible in the figure and
    is mush at 280px, while four runtimes on two benchmarks still carries
    the claim the headline makes.

    Dark on purpose. The figures are light because they sit in the text
    column; this one sits in someone else's timeline and has to win against
    whatever is around it. The tints are replaced by solid brightened hues,
    since a pale fill on a dark ground loses its outline and its contrast.

    Authored in a 1200x630 space and rasterised at 2x for retina.
    """
    res = parse(os.path.join(HERE, "raw_langs.yaml"))
    med = {b: {k: statistics.median(v) for k, v in r.items()}
           for b, r in res.items() if b != "startup"}

    CW, CH = 1200, 630
    BG_D, FG_D = "#0b0e14", "#e6edf3"
    DIM_D, RULE_D = "#8b949e", "#30363d"

    # The figure's ramp, brightened to hold up on a dark ground
    RUNTIMES = [("CPython", "python", "#9aa5b1"), ("CRuby", "ruby", "#c99cff"),
                ("Lua", "lua", "#3fdd9e"), ("Plush", "plush_new", "#ff7a4d")]
    BENCHES = [("binary_tree", "binary_tree"), ("fib(38)", "fib")]

    # sips only resolves a bare font name: a quoted stack falls back to sans
    MONO, ADV = "Menlo", 0.6022

    def ctext(x, y, s, size, fill=FG_D, anchor="start", weight=None):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{MONO}" '
                f'font-size="{size}" fill="{fill}" text-anchor="{anchor}"'
                + (f' font-weight="{weight}"' if weight else "")
                + f'>{esc(s)}</text>\n')

    def cwidth(s, size):
        return len(s) * size * ADV

    M = 60
    b = rect(0, 0, CW, CH, BG_D)

    seg = CW / 4.0
    for i, (_, _, col) in enumerate(RUNTIMES):
        b += rect(i * seg, 0, seg + 1, 9, col)

    HEAD = 46
    l1 = "My New Register-Based Interpreter"
    l2 = "can now beat Lua"
    for ln in (l1, l2):
        assert cwidth(ln, HEAD) <= CW - 2 * M, f"headline too wide: {ln}"
    b += ctext(M, 112, l1, HEAD, FG_D, weight="bold")
    b += ctext(M, 170, l2, HEAD, "#ff7a4d", weight="bold")

    BAR_W, BAR_GAP, GROUP_GAP = 112.0, 14.0, 100.0
    BASE, PLOT_H = 470.0, 232.0
    group_w = 4 * BAR_W + 3 * BAR_GAP
    span = 2 * group_w + GROUP_GAP
    assert span <= CW - 2 * M, f"bars need {span:.0f}px"
    hi = 3.1

    x = M + (CW - 2 * M - span) / 2
    ref_y = BASE - PLOT_H / hi

    # A bar under 1.00x puts its label on the reference line, so the labels
    # are held back and drawn last, each on a pad of the background
    vlabels = ""
    for lab, key in BENCHES:
        for name, runner, col in RUNTIMES:
            v = med[key]["python"] / med[key][runner]
            h = PLOT_H * v / hi
            b += rect(x, BASE - h, BAR_W, h, col)
            s, cx, ly = f"{v:.2f}x", x + BAR_W / 2, BASE - h - 14
            vlabels += rect(cx - cwidth(s, 26) / 2 - 5, ly - 24,
                            cwidth(s, 26) + 10, 30, BG_D)
            vlabels += ctext(cx, ly, s, 26, col, "middle", weight="bold")
            b += ctext(cx, BASE + 30, name, 20, DIM_D, "middle")
            x += BAR_W + BAR_GAP
        b += ctext(x - BAR_GAP - group_w / 2, BASE + 60, lab, 22, FG_D,
                   "middle", weight="bold")
        x += GROUP_GAP - BAR_GAP

    b += line(M, BASE, CW - M, BASE, RULE_D, 2.0)
    b += line(M, ref_y, CW - M, ref_y, DIM_D, 2.0, "8 6")
    b += vlabels

    y = BASE + 88
    b += line(M, y, CW - M, y, RULE_D, 1.4)
    b += ctext(M, y + 34, "github.com/maximecb/plush", 18, DIM_D)
    b += ctext(CW - M, y + 34, "pointersgonewild.com", 18, DIM_D, "end")
    assert y + 34 + 12 <= CH, "the footer runs off the bottom"

    body = svg(CW, CH, b, cap=False)
    body = body.replace(f'width="{CW}" height="{CH}" viewBox',
                        f'width="{CW * 2}" height="{CH * 2}" viewBox', 1)
    open(os.path.join(HERE, "cover.svg"), "w").write(body)
    print(f"cover.svg: {CW * 2}x{CH * 2}")


if __name__ == "__main__":
    bytecode()
    insn_word()
    interp_speedup()
    langs()
    cover()

#!/usr/bin/env python3
"""Compare two plush builds on the benchmark suite.

The point of this script is that a speedup number is only worth printing if
the two builds were measured under the same conditions, and on a laptop they
are not. The machine heats up, the fans spin up late, something wakes up in
the background. Run every benchmark on build A and then every benchmark on
build B and the drift lands entirely on B.

So the two builds are interleaved at the innermost level. Within a round, a
benchmark is run on both builds back to back, and the order of the pair is
swapped on odd rounds so that neither build is systematically the one that
runs on a warmer core. Whatever drifts over a round drifts over both.

The speedup for a benchmark is the median of its per round ratios, where a
round's ratio is the old time over the new time from that same round.

Best of N per build looks like the obvious choice, since the noise is one
sided: nothing makes a run faster than the machine is capable of. It is the
wrong choice here, and measurably so. The machine drifts slower over a run
(alloc_objs on the baseline went 3.31, 3.87, 3.85, 3.88, 3.93 across five
rounds), so the coolest slot in the whole session belongs to whichever build
happens to run first, and best-of hands that one lucky sample straight to the
summary. That put ping_pong at 0.90x, a regression that disappears once the
rounds are paired.

Taking the ratio inside a round instead compares two runs that sat next to
each other in time, so whatever the machine was doing applies to both. The
median across rounds then throws out the rounds where something interfered.

Peak RSS comes from wait4, which reports rusage for one specific child rather
than the running maximum over all children that RUSAGE_CHILDREN gives you.
ru_maxrss is bytes on macOS and kilobytes on Linux.

Usage:
    ./bench.py --old PATH --new PATH [--benchdir DIR] [--rounds N]
               [--out results.json]
"""

import argparse
import json
import os
import statistics
import sys
import time
from math import exp, log

# The suite as it stood at both revisions. Kept explicit rather than globbed
# so that a benchmark added to the repo later cannot silently join the set
# and change the geomean.
BENCHMARKS = [
    "alloc_objs", "arr_get", "binary_tree", "fft", "fib", "for_loop",
    "gc_alloc_speed", "gc_many_objs", "host_calls", "linked_list",
    "matrix_vec_mult", "mlp", "nbody", "obj_get", "ping_pong", "quicksort",
    "sha256",
]

# sha256 is measured twice. The version in the tree at 6b71f8c shifts a
# 32-bit value left by 30, which needs bit 62 and so no longer fits in a
# fixnum; the fixed version masks first. sha256_fixed is the honest benchmark
# and is the one that goes in the headline numbers. sha256_unfixed is kept
# because what it does to the memory result is the whole point of the section
# on the cost of two tag bits.
SHA_VARIANTS = ["sha256_unfixed", "sha256_fixed"]

MAXRSS_UNIT = 1 if sys.platform == "darwin" else 1024  # to bytes

# A benchmark only counts toward the speed geomean if the baseline spends at
# least this long in it. fft does 1024 samples and matrix_vec_mult is over in
# 20ms, so for both of them the wall time is mostly process startup, which is
# the same in both builds and would pull the geomean toward 1.0 while
# measuring nothing about the VM. Peak RSS is still reported for them.
MIN_TIME = 0.200


def run_once(binary, script, cwd):
    """Run one benchmark once. Returns (wall seconds, peak RSS bytes)."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        t0 = time.perf_counter()
        pid = os.posix_spawn(
            binary, [binary, script], os.environ,
            file_actions=[(os.POSIX_SPAWN_DUP2, devnull, 1),
                          (os.POSIX_SPAWN_DUP2, devnull, 2)],
        )
        _, status, ru = os.wait4(pid, 0)
        wall = time.perf_counter() - t0
    finally:
        os.close(devnull)

    if not (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0):
        raise RuntimeError(f"{binary} {script} failed, status {status}")

    return wall, ru.ru_maxrss * MAXRSS_UNIT


def geomean(xs):
    return exp(sum(log(x) for x in xs) / len(xs))


def measure(builds, jobs, rounds, warmup):
    """Interleaved rounds over every (benchmark, build) pair."""
    times = {(n, b): [] for n in jobs for b in builds}
    rss = {(n, b): [] for n in jobs for b in builds}
    names = list(builds)

    for r in range(-warmup, rounds):
        tag = "warmup" if r < 0 else f"round {r + 1}/{rounds}"
        for name, script in jobs.items():
            # Swap which build goes first on alternating rounds so neither
            # one is always the one that runs on the warmer core.
            order = names if r % 2 == 0 else names[::-1]
            line = []
            for b in order:
                w, m = run_once(builds[b], script, None)
                if r >= 0:
                    times[(name, b)].append(w)
                    rss[(name, b)].append(m)
                line.append(f"{b} {w:6.3f}s {m / 1e6:6.1f}MB")
            print(f"  [{tag}] {name:16s} " + "  ".join(line), flush=True)

    return times, rss


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, help="baseline plush binary")
    ap.add_argument("--new", required=True, help="plush binary under test")
    ap.add_argument("--benchdir", required=True, help="dir of .psh benchmarks")
    ap.add_argument("--variants", default=None,
                    help="dir holding the two sha256 variants")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    builds = {"old": os.path.abspath(args.old), "new": os.path.abspath(args.new)}

    jobs = {n: os.path.join(os.path.abspath(args.benchdir), n + ".psh")
            for n in BENCHMARKS}
    if args.variants:
        for n in SHA_VARIANTS:
            jobs[n] = os.path.join(os.path.abspath(args.variants), n + ".psh")

    for n, p in jobs.items():
        if not os.path.exists(p):
            sys.exit(f"missing benchmark: {p}")

    print(f"{len(jobs)} benchmarks, {args.rounds} rounds "
          f"(+{args.warmup} warmup), interleaved\n")
    times, rss = measure(builds, jobs, args.rounds, args.warmup)

    # Best of N for time. Median for RSS: peak RSS is nearly deterministic,
    # so the spread is measurement noise rather than a one sided tail, and
    # the median is a fairer summary of it than the minimum.
    out = {}
    for n in jobs:
        to_all, tn_all = times[(n, "old")], times[(n, "new")]
        ratios = [a / b for a, b in zip(to_all, tn_all)]
        mo = statistics.median(rss[(n, "old")])
        mn = statistics.median(rss[(n, "new")])
        out[n] = {
            "time_old": statistics.median(to_all),
            "time_new": statistics.median(tn_all),
            "speedup": statistics.median(ratios),
            "speedup_spread": max(ratios) - min(ratios),
            "speedup_rounds": ratios,
            "speedup_bestof": min(to_all) / min(tn_all),
            "rss_old": mo, "rss_new": mn, "rss_ratio": mo / mn,
            "time_old_all": to_all, "time_new_all": tn_all,
            "rss_old_all": rss[(n, "old")], "rss_new_all": rss[(n, "new")],
        }

    # The headline set is the 17 benchmarks. When the variants were measured,
    # sha256_fixed stands in for the in-tree sha256, which is the unfixed one.
    headline = list(BENCHMARKS)
    if "sha256_fixed" in out:
        headline = [n if n != "sha256" else "sha256_fixed" for n in headline]
        del out["sha256"]

    timed = [n for n in headline if out[n]["time_old"] >= MIN_TIME]
    skipped = [n for n in headline if n not in timed]

    speed = [out[n]["speedup"] for n in timed]
    memr = [out[n]["rss_ratio"] for n in headline]

    summary = {
        "rounds": args.rounds,
        "n_timed": len(timed),
        "n_rss": len(headline),
        "too_short_for_timing": skipped,
        "speedup_geomean": geomean(speed),
        "speedup_geomean_bestof": geomean([out[n]["speedup_bestof"] for n in timed]),
        "speedup_min": min(speed),
        "speedup_max": max(speed),
        "rss_geomean": geomean(memr),
    }

    print("\n== per benchmark ==")
    print(f"{'benchmark':18s} {'old s':>8s} {'new s':>8s} {'x':>6s} {'+-':>5s}"
          f" {'old MB':>9s} {'new MB':>9s} {'x':>6s}")
    for n in headline + [v for v in SHA_VARIANTS
                         if v in out and v not in headline]:
        d = out[n]
        mark = "" if n in timed or n not in headline else "  (too short to time)"
        # A wide spread across rounds means the median is standing on noise
        if d["speedup_spread"] > 0.10 and n in timed:
            mark += "  (noisy)"
        print(f"{n:18s} {d['time_old']:8.3f} {d['time_new']:8.3f}"
              f" {d['speedup']:6.2f} {d['speedup_spread']:5.2f}"
              f" {d['rss_old'] / 1e6:9.1f}"
              f" {d['rss_new'] / 1e6:9.1f} {d['rss_ratio']:6.2f}{mark}")

    print(f"\nspeedup geomean  {summary['speedup_geomean']:.4f}x"
          f"  over {len(timed)} benchmarks"
          f"  (min {summary['speedup_min']:.2f}x,"
          f" max {summary['speedup_max']:.2f}x)")
    print(f"  best-of-N for comparison: "
          f"{summary['speedup_geomean_bestof']:.4f}x, which is the biased one")
    if skipped:
        print(f"  excluded from timing, under {MIN_TIME * 1000:.0f}ms:"
              f" {', '.join(skipped)}")
    print(f"peak RSS geomean {summary['rss_geomean']:.4f}x"
          f"  over {len(headline)} benchmarks")

    # FIXME: record provenance here: the two binary paths with their sizes and
    # mtimes, the commit each was built from, and the cargo profile. Without it
    # a results.json can't be traced back to the builds that produced it.
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "benchmarks": out}, f, indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

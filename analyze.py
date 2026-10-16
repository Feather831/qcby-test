# -*- coding: utf-8 -*-
"""Course-selection failure analysis.

Reads course_requests.csv and evaluates a "mark as seats-tight" rule against
the stated accounting:
  - each 余量不足 failure costs 90 s
  - each early "名额紧张" marking costs 15 s
"""
import csv
from datetime import datetime

DATA = "course_requests.csv"


def parse(t):
    return datetime.fromisoformat(t)


def load():
    rows = list(csv.DictReader(open(DATA, encoding="utf-8")))
    for r in rows:
        rt = parse(r["request_time"])
        bs = parse(r["balance_synced_at"].replace("Z", "+00:00"))
        r["_lag"] = int((rt - bs).total_seconds())   # staleness of displayed seats, seconds
        r["_ds"] = int(r["display_seats"])
        r["_qps"] = int(r["qps_instant"])
    return rows


def main():
    rows = load()
    F = sum(1 for r in rows if r["select_success"] == "0")
    OK = sum(1 for r in rows if r["select_success"] == "1")
    TMO = sum(1 for r in rows if r["select_success"] == "")
    print(f"total={len(rows)} success={OK} fail={F} timeout={TMO}")
    print(f"baseline failure cost = {F} * 90 = {F * 90}s")
    print()

    lags = sorted(set(r["_lag"] for r in rows))

    # failure rate by staleness band
    print("failure rate by staleness:")
    bands = [(0, 480), (480, 720), (720, 900), (900, 1200), (1200, 1800), (1800, 3600)]
    for lo, hi in bands:
        sub = [r for r in rows if lo < r["_lag"] <= hi]
        f = sum(1 for r in sub if r["select_success"] == "0")
        print(f"  {lo+1:5d}-{hi:5d}s  n={len(sub):4d} fail={f:3d} rate={f/len(sub):.3f}")
    print()

    # best staleness-only threshold
    best = []
    for T in lags:
        marked = [r for r in rows if r["_lag"] >= T]
        TP = sum(1 for r in marked if r["select_success"] == "0")
        M = len(marked)
        saving = 90 * TP - 15 * M
        best.append((saving, T, M, TP))
    best.sort(reverse=True)
    print("Top staleness-only thresholds (mark when lag >= T):")
    for saving, T, M, TP in best[:8]:
        print(f"  T>={T:5d}s  marked={M:4d} TP={TP:3d} saving={saving:6d}s")
    print()

    # grid search (staleness AND display_seats)
    cands = []
    for T in lags:
        for S in range(0, 31):
            marked = [r for r in rows if r["_lag"] >= T and r["_ds"] <= S]
            TP = sum(1 for r in marked if r["select_success"] == "0")
            M = len(marked)
            saving = 90 * TP - 15 * M
            cands.append((saving, T, S, M, TP))
    cands.sort(reverse=True)
    print("Top combined thresholds (mark when lag>=T AND display_seats<=S):")
    for saving, T, S, M, TP in cands[:12]:
        print(f"  T>={T:5d}s & ds<={S:2d}  marked={M:4d} TP={TP:3d} saving={saving:6d}s")


    # headline: recommended rule "mark 名额紧张 when staleness >= 900s (15 min)"
    print()
    print("=== recommended rule: mark when staleness >= 900 s (15 min) ===")
    T = 900
    marked = [r for r in rows if r["_lag"] >= T]
    TP = sum(1 for r in marked if r["select_success"] == "0")
    FP = sum(1 for r in marked if r["select_success"] == "1")
    MT = sum(1 for r in marked if r["select_success"] == "")
    M = len(marked)
    saving = 90 * TP - 15 * M
    remaining = (F - TP) * 90 + M * 15
    print(f"marked={M}  caught_failures(TP)={TP}  false_positive(FP)={FP}  marked_timeout={MT}")
    print(f"failure share caught = {TP}/{F} = {TP/F:.1%}")
    print(f"request share flagged = {M}/{len(rows)} = {M/len(rows):.1%}")
    print(f"net saving = 90*{TP} - 15*{M} = {saving}s  (baseline {F*90}s -> {remaining}s, {saving/(F*90):.1%} reduction)")


if __name__ == "__main__":
    main()

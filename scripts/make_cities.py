#!/usr/bin/env python3
"""Makes countries.csv and cities/<ISO2>.csv from GeoNames (cities15000.txt, countryInfo.txt and admin1CodesASCII.txt, CC BY 4.0,
https://www.geonames.org).

    python3 scripts/make_cities.py <folder with the GeoNames files> [<repo folder>]

admin1CodesASCII.txt is optional but should be there: it gives each city its region (state, province, ...), which the app shows after the
name ("Curitiba, Paraná").
A city name must be unique per country, since a submission names its city by that name alone. A name that occurs twice gets its region
into the name ("São José, Santa Catarina") and the admin1 column stays empty, so the app does not show the region twice. Equal names in one
region (or without a region): the most populous keeps the name, the others get their position ("São José, Santa Catarina [-28.21, -49.16]").
The channel files (<mode>/<ISO2>.csv) follow: a city that is renamed is renamed there too, found by its position.
"""
import csv, os, sys
from collections import Counter

MODES = ("atsc", "atsc3", "dab", "dtmb", "dvb-t", "fm", "isdb-t")   # folders with a city column


def read_csv(path):
    if not os.path.exists(path): return []
    with open(path, encoding="utf-8", newline="") as fh: return list(csv.reader(fh))


def unique_names(rows):
    """rows: [name, admin1, lat, lon, population]; makes the names unique (see the top of this file)."""
    count = Counter(r[0] for r in rows)
    for r in rows:
        if count[r[0]] > 1 and r[1]:
            r[0] = "%s, %s" % (r[0], r[1])
            r[1] = ""
    count = Counter(r[0] for r in rows)
    seen = set()
    for r in sorted(rows, key=lambda r: -int(r[4] or 0)):
        if count[r[0]] > 1:
            if r[0] in seen: r[0] = "%s [%.2f, %.2f]" % (r[0], float(r[2]), float(r[3]))
            seen.add(r[0])


def rename_channels(out, cc, old, new):
    """old, new: the rows of cities/<cc>.csv before and after; renames the cities in the channel files by position."""
    pos = {(r[2], r[3]): r[0] for r in new}
    near = [(float(r[2]), float(r[3]), r[0]) for r in new]
    names = {r[0] for r in new}
    ren = {}
    for r in old:
        if r[0] in names: continue
        to = pos.get((r[2], r[3]))
        if to is None:   # moved a little in a newer GeoNames dump
            la, lo = float(r[2]), float(r[3])
            d, to = min(((abs(a - la) + abs(b - lo), n) for a, b, n in near), default=(1, None))
            if d > 0.05: to = None
        if to: ren[r[0]] = to
    for mode in MODES:
        path = os.path.join(out, mode, cc + ".csv")
        rows = read_csv(path)
        if len(rows) < 2 or not any(r and r[0] in ren for r in rows[1:]): continue
        body = [[ren.get(r[0], r[0])] + r[1:] for r in rows[1:] if r]
        body.sort(key=lambda r: (r[0], float(r[1])))
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(rows[0]); w.writerows(body)
        print("%s: %d row(s) renamed" % (os.path.relpath(path, out), sum(1 for r in rows[1:] if r and r[0] in ren)))
    for mode in MODES:
        for r in read_csv(os.path.join(out, mode, cc + ".csv"))[1:]:
            if r and r[0] not in names and r[0] not in ren: print("warning: %s/%s.csv names '%s', which is no longer a city" % (mode, cc, r[0]))


def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    admin = {}
    p = os.path.join(src, "admin1CodesASCII.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2: admin[f[0]] = f[1]
    else:
        print("warning: no admin1CodesASCII.txt, the cities get no region")
    names = {}
    for line in open(os.path.join(src, "countryInfo.txt"), encoding="utf-8"):
        if line.startswith("#") or not line.strip(): continue
        f = line.rstrip("\n").split("\t")
        names[f[0]] = f[4]
    by = {}
    for line in open(os.path.join(src, "cities15000.txt"), encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) < 15: continue
        cc = f[8]
        by.setdefault(cc, []).append([f[1], admin.get(cc + "." + f[10], ""), f[4], f[5], f[14]])
    os.makedirs(os.path.join(out, "cities"), exist_ok=True)
    old = {}
    for name in os.listdir(os.path.join(out, "cities")):
        if name.endswith(".csv"):
            old[name[:-4]] = [r for r in read_csv(os.path.join(out, "cities", name))[1:] if r]
            os.remove(os.path.join(out, "cities", name))
    countries = []
    for cc in sorted(by):
        rows = by[cc]
        unique_names(rows)
        rows.sort(key=lambda r: r[0])
        with open(os.path.join(out, "cities", cc + ".csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["name", "admin1", "lat", "lon", "population"])
            w.writerows(rows)
        rename_channels(out, cc, old.get(cc, []), rows)
        countries.append((cc, names.get(cc, cc)))
    with open(os.path.join(out, "countries.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["iso2", "name"])
        w.writerows(countries)
    print("%d countries, %d cities" % (len(countries), sum(len(v) for v in by.values())))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Makes countries.csv and cities/<ISO2>.csv from GeoNames (cities15000.txt and countryInfo.txt, CC BY 4.0, https://www.geonames.org).

    python3 scripts/make_cities.py <folder with the two GeoNames files> [<repo folder>]

Optional in the same folder: admin1CodesASCII.txt, which adds the region name (admin1) to each city.
Names that occur twice in a country get the region name or code (or, without one, the position) in brackets, so a city name is unique per country:
the ingest script finds a city by that name.
"""
import csv, os, sys
from collections import Counter

def main():
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    admin = {}
    p = os.path.join(src, "admin1CodesASCII.txt")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 2: admin[f[0]] = f[1]
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
        a1 = admin.get(cc + "." + f[10], "")
        by.setdefault(cc, []).append([f[1], a1, f[4], f[5], f[14], f[10]])   # last: the region code, for telling equal names apart
    os.makedirs(os.path.join(out, "cities"), exist_ok=True)
    for old in os.listdir(os.path.join(out, "cities")):
        if old.endswith(".csv"): os.remove(os.path.join(out, "cities", old))
    countries = []
    for cc in sorted(by):
        rows = by[cc]
        count = Counter(r[0] for r in rows)
        for r in rows:
            if count[r[0]] > 1:
                r[0] = "%s (%s)" % (r[0], r[1] or r[5] or "%.1f, %.1f" % (float(r[2]), float(r[3])))
        # still not unique (same region): add the position
        count = Counter(r[0] for r in rows)
        for r in rows:
            if count[r[0]] > 1: r[0] = "%s [%.2f, %.2f]" % (r[0], float(r[2]), float(r[3]))
        rows.sort(key=lambda r: r[0])
        with open(os.path.join(out, "cities", cc + ".csv"), "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["name", "admin1", "lat", "lon", "population"])
            w.writerows(r[:5] for r in rows)
        countries.append((cc, names.get(cc, cc)))
    with open(os.path.join(out, "countries.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["iso2", "name"])
        w.writerows(countries)
    print("%d countries, %d cities" % (len(countries), sum(len(v) for v in by.values())))

if __name__ == "__main__":
    main()

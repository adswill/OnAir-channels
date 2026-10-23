#!/usr/bin/env python3
"""Removes '?' placeholders and repeated names from the services of the data files (what check_data.py warns about): python3 scripts/tidy.py [--repo .]"""
import argparse, glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest

ap = argparse.ArgumentParser()
ap.add_argument("--repo", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
a = ap.parse_args()
changed = 0
for mode in sorted(ingest.BANDS):
    for path in sorted(glob.glob(os.path.join(a.repo, mode, "*.csv"))):
        db = ingest.load_db(path)
        before = [list(d["services"]) for d in db]
        for d in db:
            d["services"] = ingest.clean_services("|".join(d["services"]))
        if before != [d["services"] for d in db]:
            ingest.write_db(path, db)
            changed += 1
            print("tidied", os.path.relpath(path, a.repo))
print("%d file(s) changed" % changed)

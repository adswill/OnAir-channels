#!/usr/bin/env python3
"""Checks one submission (the text of a GitHub issue) and merges it into <mode>/<ISO2>.csv.

    python3 scripts/ingest.py --repo . --body-file body.txt [--date YYYY-MM-DD] [--result result.json]

Exit code 0: merged (the file is written). 1: the submission is invalid (nothing written). The message is printed and, with --result,
written as {"ok": bool, "message": str, "path": str}. The workflow comments with it. The rules are the ones of the OnAir app
(core/src/channel_db.cpp): same city and frequency within 0.05 MHz is the same channel.
"""
import argparse, csv, datetime, io, json, os, re, sys

# frequency ranges (MHz) a channel of each mode can be in; wide on purpose, the point is to catch typos and junk
BANDS = {
    "dvb-t": [(170, 870)],
    "atsc": [(50, 900)],
    "atsc3": [(50, 900)],
    "isdb-t": [(170, 900)],
    "dtmb": [(48, 870)],
    "dab": [(170, 240), (1452, 1492)],
    "fm": [(64, 110)],
}
MAX_ROWS = 300
SAME_MHZ = 0.05
HEADER = ["city", "freq_mhz", "bw_mhz", "standard", "network", "services", "snr_db", "reports", "first_seen", "last_seen"]


class Invalid(Exception):
    pass


def fmt_freq(v):
    s = "%.3f" % v
    while len(s) > 2 and s.endswith("0") and s[-2] != ".":
        s = s[:-1]
    return s


def fmt_snr(v):
    return "%.1f" % v


def split_services(s):
    return [x.strip() for x in s.split("|") if x.strip()]


def parse_body(text):
    """mode / country / city lines and the first fenced block (as the app writes it, or inside an issue form's rendering)."""
    head = {}
    block, in_block, have = [], False, False
    for line in text.replace("\r\n", "\n").split("\n"):
        t = line.strip()
        if t.startswith("```"):
            if in_block:
                have = True
                break
            in_block = True
            continue
        if in_block:
            block.append(t)
            continue
        m = re.match(r"^(mode|country|city):\s*(.*)$", t)
        if m and m.group(1) not in head:
            head[m.group(1)] = m.group(2).strip()
    if not have:
        raise Invalid("No ```csv block found in the issue.")
    for k in ("mode", "country", "city"):
        if not head.get(k):
            raise Invalid("The line '%s: ...' is missing." % k)
    rows = []
    for i, r in enumerate(csv.reader(io.StringIO("\n".join(block)))):
        if not r:
            continue
        if i == 0 and r[0].strip() == "freq_mhz":
            continue
        if len(r) < 6:
            raise Invalid("Row %d has %d fields, expected 6 (freq_mhz,bw_mhz,standard,network,services,snr_db)." % (len(rows) + 1, len(r)))
        try:
            rows.append({
                "freq": float(r[0]), "bw": float(r[1]), "standard": r[2].strip(), "network": r[3].strip(),
                "services": split_services(r[4]), "snr": float(r[5]),
            })
        except ValueError:
            raise Invalid("Row %d: frequency, bandwidth or SNR is not a number." % (len(rows) + 1))
    return head["mode"], head["country"].upper(), head["city"], rows


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.reader(fh))


def city_names(repo, cc):
    return {r[0] for r in read_csv(os.path.join(repo, "cities", cc + ".csv"))[1:] if r}


def validate(repo, mode, cc, city, rows):
    if mode not in BANDS or not os.path.isdir(os.path.join(repo, mode)):
        raise Invalid("Unknown mode '%s'. Known: %s." % (mode, ", ".join(sorted(BANDS))))
    known = {r[0] for r in read_csv(os.path.join(repo, "countries.csv"))[1:] if r}
    if cc not in known:
        raise Invalid("Unknown country code '%s' (see countries.csv)." % cc)
    if city not in city_names(repo, cc):
        raise Invalid("The city '%s' is not in cities/%s.csv." % (city, cc))
    if not rows:
        raise Invalid("The submission has no channels.")
    if len(rows) > MAX_ROWS:
        raise Invalid("Too many channels (%d, at most %d)." % (len(rows), MAX_ROWS))
    for n, r in enumerate(rows, 1):
        if not any(lo <= r["freq"] <= hi for lo, hi in BANDS[mode]):
            raise Invalid("Row %d: %.3f MHz is outside the %s band." % (n, r["freq"], mode))
        if not (0 < r["bw"] <= 10):
            raise Invalid("Row %d: bandwidth %.3f MHz is not between 0 and 10." % (n, r["bw"]))
        if not (-30 <= r["snr"] <= 60):
            raise Invalid("Row %d: SNR %.1f dB is not between -30 and 60." % (n, r["snr"]))
        if len(r["standard"]) > 30 or len(r["network"]) > 120 or len(r["services"]) > 80 or any(len(s) > 120 for s in r["services"]):
            raise Invalid("Row %d: a text is too long." % n)
        for t in [r["standard"], r["network"]] + r["services"]:
            if any(ord(c) < 32 for c in t):
                raise Invalid("Row %d: control characters in a text." % n)


def same(a, b):
    return abs(a["freq"] - b["freq"]) <= SAME_MHZ


def merge(db, city, new, date):
    uniq = []
    for r in new:  # one submission counts once per channel
        for u in uniq:
            if same(u, r):
                u["snr"] = max(u["snr"], r["snr"])
                u["services"] += [s for s in r["services"] if s not in u["services"]]
                break
        else:
            uniq.append(dict(r, services=list(r["services"])))
    for r in uniq:
        hit = next((d for d in db if d["city"] == city and same(d, r)), None)
        if hit:
            hit["reports"] += 1
            hit["last"] = date
            hit["snr"] = max(hit["snr"], r["snr"])
            hit["services"] += [s for s in r["services"] if s not in hit["services"]]
            hit["standard"] = hit["standard"] or r["standard"]
            hit["network"] = hit["network"] or r["network"]
            if hit["bw"] <= 0:
                hit["bw"] = r["bw"]
        else:
            db.append(dict(r, city=city, reports=1, first=date, last=date))


def load_db(path):
    db = []
    for r in read_csv(path)[1:]:
        if len(r) < 7:
            continue
        db.append({
            "city": r[0], "freq": float(r[1]), "bw": float(r[2]), "standard": r[3], "network": r[4], "services": split_services(r[5]),
            "snr": float(r[6]), "reports": int(r[7]) if len(r) > 7 and r[7] else 1, "first": r[8] if len(r) > 8 else "", "last": r[9] if len(r) > 9 else "",
        })
    return db


def write_db(path, db):
    db.sort(key=lambda d: (d["city"], d["freq"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")  # quotes only where needed (RFC 4180)
        w.writerow(HEADER)
        for d in db:
            w.writerow([d["city"], fmt_freq(d["freq"]), fmt_freq(d["bw"]), d["standard"], d["network"], "|".join(d["services"]),
                        fmt_snr(d["snr"]), d["reports"], d["first"], d["last"]])


def ingest(repo, text, date):
    mode, cc, city, rows = parse_body(text)
    validate(repo, mode, cc, city, rows)
    path = os.path.join(repo, mode, cc + ".csv")
    db = load_db(path)
    merge(db, city, rows, date)
    write_db(path, db)
    return os.path.relpath(path, repo).replace(os.sep, "/"), "%s %s %s: %d channel(s)" % (mode, cc, city, len(rows))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--body-file", required=True)
    ap.add_argument("--date", default=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--result")
    a = ap.parse_args()
    with open(a.body_file, encoding="utf-8") as fh:
        text = fh.read()
    try:
        path, msg = ingest(a.repo, text, a.date)
        res = {"ok": True, "message": msg, "path": path}
    except Invalid as e:
        res = {"ok": False, "message": str(e), "path": ""}
    print(json.dumps(res))
    if a.result:
        with open(a.result, "w", encoding="utf-8") as fh:
            json.dump(res, fh)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

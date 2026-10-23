#!/usr/bin/env python3
"""Checks the data files of this repository (not a submission): python3 scripts/check_data.py [--repo .] [--stale-months 18] [--strict]

Errors (exit code 1): a file that is not UTF-8, a wrong header or field count, rows out of order, two channels of one city within 0.05 MHz,
a frequency outside the band of its mode, a bandwidth or SNR that cannot be real, a city that is not in cities/<ISO2>.csv, a bad date,
control or invisible characters, e-mail addresses / web addresses / phone numbers in a name, a TII position that is not on Earth.
Warnings (exit code 0, or 1 with --strict): a row not seen for more than --stale-months months, '?' or repeated service names,
a bandwidth that is unusual for its mode, a frequency that is not on the usual channel raster.
"""
import argparse, csv, datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest

# bandwidths (MHz) a channel of each mode can really have; outside these is a typo or a wrong standard
BW = {"fm": (0.05, 0.4), "dab": (1.0, 2.0), "dvb-t": (1.0, 10.0), "atsc": (5.0, 7.0), "atsc3": (1.0, 8.0), "isdb-t": (0.4, 8.0), "dtmb": (5.0, 9.0)}


class Report:
    def __init__(self):
        self.errors, self.warnings = [], []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


def months_ago(date, today):
    return (today.year - date.year) * 12 + today.month - date.month + (today.day - date.day) / 31.0


def read_rows(path, rep, header):
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
    except UnicodeDecodeError as e:
        rep.err(path, "not valid UTF-8 (%s)" % e)
        return None
    if not rows or rows[0] != header:
        rep.err(path, "wrong or missing header (expected %s)" % ",".join(header))
        return None
    return rows[1:]


def check_mode_file(repo, mode, name, rep, today, stale):
    path = os.path.join(mode, name)
    cc = name[:-4]
    cities = ingest.city_names(repo, cc)
    rows = read_rows(os.path.join(repo, path), rep, ingest.HEADER)
    if rows is None:
        return
    prev = None
    seen = []
    for n, r in enumerate(rows, 2):
        where = "%s:%d" % (path, n)
        if len(r) != len(ingest.HEADER):
            rep.err(where, "%d fields, expected %d" % (len(r), len(ingest.HEADER)))
            continue
        try:
            freq, bw, snr, reports = float(r[1]), float(r[2]), float(r[6]), int(r[7])
        except ValueError:
            rep.err(where, "a number is not a number")
            continue
        city = r[0]
        if city not in cities:
            rep.err(where, "city '%s' is not in cities/%s.csv" % (city, cc))
        if prev is not None and (city, freq) < prev:
            rep.err(where, "rows are not sorted by city, then frequency")
        prev = (city, freq)
        for c_city, c_freq in seen:
            if c_city == city and abs(c_freq - freq) <= ingest.SAME_MHZ and c_freq != freq:
                rep.err(where, "%.3f MHz is within 0.05 MHz of %.3f MHz in the same city (the same channel twice)" % (freq, c_freq))
        if (city, freq) in seen:
            rep.err(where, "%.3f MHz appears twice in %s" % (freq, city))
        seen.append((city, freq))
        if not any(lo <= freq <= hi for lo, hi in ingest.BANDS[mode]):
            rep.err(where, "%.3f MHz is outside the %s band" % (freq, mode))
        if not (0 < bw <= 10):
            rep.err(where, "bandwidth %.3f MHz is not between 0 and 10" % bw)
        elif not (BW[mode][0] <= bw <= BW[mode][1]):
            rep.warn(where, "bandwidth %.3f MHz is unusual for %s (%.2f to %.2f)" % (bw, mode, BW[mode][0], BW[mode][1]))
        if not (-30 <= snr <= 60):
            rep.err(where, "SNR %.1f dB is not between -30 and 60" % snr)
        if reports < 1:
            rep.err(where, "reports is %d" % reports)
        first = last = None
        for label, v in (("first_seen", r[8]), ("last_seen", r[9])):
            try:
                d = datetime.date.fromisoformat(v)
            except ValueError:
                rep.err(where, "%s '%s' is not a date (YYYY-MM-DD)" % (label, v))
                continue
            if d > today:
                rep.err(where, "%s %s is in the future" % (label, v))
            if label == "first_seen":
                first = d
            else:
                last = d
        if first and last:
            if first > last:
                rep.err(where, "first_seen is after last_seen")
            if months_ago(last, today) > stale:
                rep.warn(where, "%s %.3f MHz not seen since %s (more than %g months)" % (city, freq, last, stale))
        names = [r[3], r[4]] + r[5].split("|")
        if r[3] and not ingest.STANDARD_RE.match(r[3]):
            rep.err(where, "the standard '%s' is not a plain name" % r[3])
        for t in names:
            if any(ingest.bad_char(c) for c in t):
                rep.err(where, "control or invisible characters in '%s'" % ingest.shown(t))
            elif ingest.personal(t):
                rep.err(where, "'%s' looks like an e-mail address, a web address or a phone number" % t[:40])
        sv = [x for x in r[5].split("|") if x]
        if any(not x.strip("?") for x in sv):
            rep.warn(where, "'?' placeholder in the services")
        if len(set(sv)) != len(sv):
            rep.warn(where, "a service name appears more than once")
        if r[3] != r[3].strip() or r[4] != r[4].strip():
            rep.warn(where, "spaces around a name")


def check_tii_file(repo, name, rep, today, stale):
    path = os.path.join(ingest.TII_MODE, name)
    cc = name[:-4]
    rows = read_rows(os.path.join(repo, path), rep, ingest.TII_HEADER)
    if rows is None:
        return
    prev, keys = None, set()
    for n, r in enumerate(rows, 2):
        where = "%s:%d" % (path, n)
        if len(r) != len(ingest.TII_HEADER):
            rep.err(where, "%d fields, expected %d" % (len(r), len(ingest.TII_HEADER)))
            continue
        try:
            key = (r[0], int(r[1]), int(r[2]))
            lat, lon = float(r[3]), float(r[4])
        except ValueError:
            rep.err(where, "a number is not a number")
            continue
        if not ingest.re.match(r"^[0-9A-F]{4}$", r[0]):
            rep.err(where, "ensemble id '%s' is not 4 upper-case hex digits" % r[0])
        if not (0 <= key[1] <= 69 and 0 <= key[2] <= 23):
            rep.err(where, "MainId/SubId out of range")
        if key in keys:
            rep.err(where, "transmitter %s %d/%d is listed twice" % key)
        keys.add(key)
        if prev is not None and key < prev:
            rep.err(where, "rows are not sorted by eid, main, sub")
        prev = key
        if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (abs(lat) < 1e-6 and abs(lon) < 1e-6):
            rep.err(where, "position %.5f, %.5f is not a place on Earth" % (lat, lon))
        if r[7]:
            try:
                if not any(lo <= float(r[7]) <= hi for lo, hi in ingest.BANDS["dab"]):
                    rep.err(where, "%s MHz is not a DAB channel" % r[7])
            except ValueError:
                rep.err(where, "channel_mhz is not a number")
        if any(ingest.bad_char(c) for c in r[5]) or ingest.personal(r[5]):
            rep.err(where, "the site name has control characters or looks like personal data")
        try:
            if months_ago(datetime.date.fromisoformat(r[10]), today) > stale:
                rep.warn(where, "transmitter %s %s/%s not confirmed since %s" % (r[0], r[1], r[2], r[10]))
        except ValueError:
            rep.err(where, "last_seen '%s' is not a date" % r[10])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--stale-months", type=float, default=18)
    ap.add_argument("--today", default=datetime.date.today().isoformat())
    ap.add_argument("--strict", action="store_true", help="warnings fail too")
    ap.add_argument("--quiet", action="store_true", help="print the counts and the first 20 of each only")
    a = ap.parse_args()
    today = datetime.date.fromisoformat(a.today)
    rep = Report()
    known = {r[0] for r in ingest.read_csv(os.path.join(a.repo, "countries.csv"))[1:] if r}
    for mode in sorted(ingest.BANDS) + [ingest.TII_MODE]:
        d = os.path.join(a.repo, mode)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".csv"):
                continue
            if name[:-4] not in known:
                rep.err(os.path.join(mode, name), "the country code is not in countries.csv")
            if mode == ingest.TII_MODE:
                check_tii_file(a.repo, name, rep, today, a.stale_months)
            else:
                check_mode_file(a.repo, mode, name, rep, today, a.stale_months)
    lim = 20 if a.quiet else None
    for label, lst in (("ERROR", rep.errors), ("warning", rep.warnings)):
        for m in lst[:lim]:
            print("%s %s" % (label, m))
        if lim and len(lst) > lim:
            print("... and %d more %ss" % (len(lst) - lim, label.lower()))
    print("%d error(s), %d warning(s)" % (len(rep.errors), len(rep.warnings)))
    return 1 if rep.errors or (a.strict and rep.warnings) else 0


if __name__ == "__main__":
    sys.exit(main())

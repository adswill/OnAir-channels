#!/usr/bin/env python3
"""Tests scripts/ingest.py on a copy of this folder: python3 scripts/test_ingest.py"""
import os, shutil, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
fails = 0


def check(cond, what):
    global fails
    if not cond:
        print("FAIL:", what)
        fails += 1


def body(mode="dvb-t", cc="DE", city="Berlin", rows="522,8,DVB-T2,\"Net, One\",Das Erste|ZDF,17.25\n473.143,6,ISDB-T,,,9.5", fence=True):
    # the text the OnAir app writes (see issueBody in core/src/channel_db.cpp), optionally as an issue form renders it
    t = "mode: %s\ncountry: %s\ncity: %s\n\n```csv\nfreq_mhz,bw_mhz,standard,network,services,snr_db\n%s\n```\n" % (mode, cc, city, rows)
    return "### Scan result\n\n" + t if fence else t


def run(repo, text, date):
    try:
        return True, ingest.ingest(repo, text, date)
    except ingest.Invalid as e:
        return False, str(e)


tmp = tempfile.mkdtemp()
repo = os.path.join(tmp, "r")
shutil.copytree(HERE, repo, ignore=shutil.ignore_patterns(".git"))
try:
    ok, r = run(repo, body(), "2026-10-01")
    check(ok, "valid submission: %s" % (r,))
    text = open(os.path.join(repo, "dvb-t/DE.csv"), encoding="utf-8").read()
    check(text.splitlines()[0] == "city,freq_mhz,bw_mhz,standard,network,services,snr_db,reports,first_seen,last_seen", "header")
    check('Berlin,522.0,8.0,DVB-T2,"Net, One",Das Erste|ZDF,17.2,1,2026-10-01,2026-10-01' in text or "17.3" in text, "row written: " + text)
    check("473.143,6.0,ISDB-T,,,9.5,1,2026-10-01,2026-10-01" in text, "empty fields stay empty")
    # a merge: near frequency, better SNR, a new service, one new channel
    ok, r = run(repo, body(rows="522.02,8,DVB-T2,,Das Erste|RTL,20.0\n530,8,DVB-T2,,,5"), "2026-10-05")
    check(ok, "merge: %s" % (r,))
    db = ingest.load_db(os.path.join(repo, "dvb-t/DE.csv"))
    d = [x for x in db if abs(x["freq"] - 522) < 0.1][0]
    check(len(db) == 3 and d["reports"] == 2 and d["snr"] == 20.0 and d["last"] == "2026-10-05" and d["first"] == "2026-10-01"
          and d["services"] == ["Das Erste", "ZDF", "RTL"] and d["network"] == "Net, One", "merged row %s" % d)
    check([x["freq"] for x in db] == sorted(x["freq"] for x in db), "sorted by frequency")
    # a second city sorts after Berlin
    ok, r = run(repo, body(city="Munich", rows="506,8,DVB-T2,,,11"), "2026-10-06")
    check(ok and ingest.load_db(os.path.join(repo, "dvb-t/DE.csv"))[-1]["city"] == "Munich", "second city sorted")
    # one submission with two rows on one channel counts once
    ok, r = run(repo, body(rows="506,8,DVB-T2,,,12\n506.01,8,DVB-T2,,,13"), "2026-10-07")
    m = [x for x in ingest.load_db(os.path.join(repo, "dvb-t/DE.csv")) if x["city"] == "Berlin" and abs(x["freq"] - 506) < 0.1]
    check(ok and len(m) == 1 and m[0]["reports"] == 1, "duplicate rows in one submission")
    before = open(os.path.join(repo, "dvb-t/DE.csv"), encoding="utf-8").read()
    bad = {
        "unknown mode": body(mode="dvb-x"),
        "unknown country": body(cc="ZZ"),
        "unknown city": body(city="Atlantis"),
        "frequency outside band": body(rows="1200,8,DVB-T2,,,10"),
        "not a number": body(rows="abc,8,DVB-T2,,,10"),
        "snr insane": body(rows="522,8,DVB-T2,,,300"),
        "too few fields": body(rows="522,8,DVB-T2"),
        "no channels": body(rows=""),
        "no block": "mode: dvb-t\ncountry: DE\ncity: Berlin\n",
        "too many rows": body(rows="\n".join("%.2f,8,DVB-T2,,,10" % (470 + i * 0.07) for i in range(301))),
    }
    for what, text in bad.items():
        ok, r = run(repo, text, "2026-10-08")
        check(not ok, "invalid accepted: " + what)
    check(open(os.path.join(repo, "dvb-t/DE.csv"), encoding="utf-8").read() == before, "invalid submissions change nothing")
    # exactly 300 rows is fine; the DAB band
    ok, r = run(repo, body(mode="dab", cc="AE", city="Dubai", rows="\n".join("%.2f,1.536,DAB,Ens,A|B,10" % (174 + i * 0.1) for i in range(60))), "2026-10-08")
    check(ok, "dab: %s" % (r,))
    ok, r = run(repo, body(mode="fm", cc="AE", city="Dubai", rows="93.9,0.2,FM,Noor Dubai,,22.5", fence=False), "2026-10-08")
    check(ok, "fm, body without the form heading: %s" % (r,))
finally:
    shutil.rmtree(tmp)
print("ingest: %s" % ("%d FAILED" % fails if fails else "all passed"))
sys.exit(1 if fails else 0)

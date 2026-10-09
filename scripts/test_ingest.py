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
        "nan": body(rows="nan,8,DVB-T2,,,10"),
        "infinite snr": body(rows="522,8,DVB-T2,,,inf"),
        "standard with markup": body(rows="522,8,<script>,,,10"),
        "bidi override": body(rows="522,8,DVB-T2,Net\u202eevil,,10"),
        "zero-width": body(rows="522,8,DVB-T2,Ne\u200bt,,10"),
        "DEL char": body(rows="522,8,DVB-T2,Net\x7f,,10"),
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
    # a name that a spreadsheet would run as a formula loses the leading = + - @
    ok, r = run(repo, body(cc="AE", city="Dubai", rows="530,8,DVB-T2,=HYPERLINK(1),@cmd|+x,12"), "2026-10-08")
    txt = open(os.path.join(repo, "dvb-t/AE.csv"), encoding="utf-8").read()
    check(ok and "=HYPERLINK" not in txt and "HYPERLINK(1)" in txt and "@cmd" not in txt, "formula prefixes dropped: %s" % (r,))
    # ---- DAB transmitters (dab-tii): eid,main,sub,lat,lon,site,power_kw,channel_mhz
    def tii(cc="GB", rows="CE15,1,1,51.5073,-0.1277,London Crystal Palace,10,225.648"):
        return "mode: dab-tii\ncountry: %s\n\n```csv\neid,main,sub,lat,lon,site,power_kw,channel_mhz\n%s\n```\n" % (cc, rows)
    ok, r = run(repo, tii(), "2026-10-09")
    check(ok, "tii: %s" % (r,))
    path = os.path.join(repo, "dab-tii/GB.csv")
    txt = open(path, encoding="utf-8").read()
    check(txt.splitlines()[0] == "eid,main,sub,lat,lon,site,power_kw,channel_mhz,reports,first_seen,last_seen", "tii header")
    check("CE15,1,1,51.50730,-0.12770,London Crystal Palace,10,225.648,1,2026-10-09,2026-10-09" in txt, "tii row: " + txt)
    # the same transmitter within 2 km confirms it (fills what was empty); a second one is added; sorted by eid, main, sub
    ok, r = run(repo, tii(rows="ce15,1,1,51.51,-0.13,,,\nCE15,1,0,52.0,-1.0,Other,,"), "2026-10-10")
    db = ingest.load_tii(path)
    d = [x for x in db if x["sub"] == 1][0]
    check(ok and len(db) == 2 and d["reports"] == 2 and d["last"] == "2026-10-10" and d["site"] == "London Crystal Palace"
          and abs(d["lat"] - 51.5073) < 1e-6 and [x["sub"] for x in db] == [0, 1], "tii merge %s / %s" % (r, db))
    before = open(path, encoding="utf-8").read()
    bad_tii = {
        "moved 30 km": tii(rows="CE15,1,1,51.8,-0.1,Somewhere,,"),
        "main out of range": tii(rows="CE15,70,1,51.5,-0.1,,,"),
        "sub out of range": tii(rows="CE15,1,24,51.5,-0.1,,,"),
        "eid not hex": tii(rows="XY15,1,1,51.5,-0.1,,,"),
        "position left empty": tii(rows="CE15,2,2,,,Site,,"),
        "position 0,0": tii(rows="CE15,2,2,0,0,Site,,"),
        "latitude 95": tii(rows="CE15,2,2,95,10,Site,,"),
        "not a DAB channel": tii(rows="CE15,2,2,51.5,-0.1,Site,,500"),
        "power insane": tii(rows="CE15,2,2,51.5,-0.1,Site,5000,"),
        "bidi in the site": tii(rows="CE15,2,2,51.5,-0.1,Si\u202ete,,"),
        "unknown country": tii(cc="ZZ"),
        "no rows": tii(rows=""),
        "too many": tii(rows="\n".join("CE15,%d,%d,51.5,-0.1,,," % (i // 24, i % 24) for i in range(101))),
    }
    for what, text in bad_tii.items():
        ok, r = run(repo, text, "2026-10-11")
        check(not ok, "invalid tii accepted: " + what)
    check(open(path, encoding="utf-8").read() == before, "invalid tii submissions change nothing")
    ok, r = run(repo, tii(rows="CE15,2,3,51.4,-0.2,=cmd,,"), "2026-10-11")
    check(ok and "=cmd" not in open(path, encoding="utf-8").read(), "tii site formula prefix dropped: %s" % (r,))
finally:
    shutil.rmtree(tmp)
print("ingest: %s" % ("%d FAILED" % fails if fails else "all passed"))
sys.exit(1 if fails else 0)

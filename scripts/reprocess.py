#!/usr/bin/env python3
"""Runs today's checks again on the submissions that were refused (or never processed) and shows which would pass now.

    python3 scripts/reprocess.py                 # fetch the open issues labelled 'invalid' with gh and report; changes nothing
    python3 scripts/reprocess.py --apply         # also merge the ones that pass into the CSV files of this folder (review the diff, commit by hand)
    python3 scripts/reprocess.py --numbers 124 130 --issues-dir DIR   # only these, from DIR/<number>.json (as `gh issue view N --json number,title,body,createdAt`)

Each issue is merged with its own creation date as the date seen, oldest first. Nothing is posted to GitHub: closing issues and writing to
the submitters stays a decision for a person.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest


def fetch(numbers, directory, repo_name):
    if directory:
        return [json.load(open(os.path.join(directory, "%s.json" % n), encoding="utf-8")) for n in numbers]
    if numbers:
        return [json.loads(subprocess.check_output(["gh", "issue", "view", str(n), "--repo", repo_name, "--json", "number,title,body,createdAt"])) for n in numbers]
    out = subprocess.check_output(["gh", "issue", "list", "--repo", repo_name, "--state", "open", "--label", "invalid", "--limit", "200",
                                   "--json", "number,title,body,createdAt"])
    return json.loads(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    ap.add_argument("--repo-name", default="adswill/OnAir-channels")
    ap.add_argument("--numbers", nargs="*", type=int, default=[])
    ap.add_argument("--issues-dir")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    issues = sorted(fetch(a.numbers, a.issues_dir, a.repo_name), key=lambda i: i["createdAt"])
    work = a.repo
    tmp = None
    if not a.apply:
        tmp = tempfile.mkdtemp()
        work = os.path.join(tmp, "r")
        shutil.copytree(a.repo, work, ignore=shutil.ignore_patterns(".git"))
    passed = 0
    try:
        for i in issues:
            try:
                path, msg = ingest.ingest(work, i["body"] or "", i["createdAt"][:10])
                print("#%-4d WOULD PASS  %s" % (i["number"], msg))
                passed += 1
            except ingest.Invalid as e:
                print("#%-4d still fails %s" % (i["number"], e))
    finally:
        if tmp:
            shutil.rmtree(tmp)
    print("%d of %d would pass%s" % (passed, len(issues), "; merged into this folder" if a.apply else " (nothing changed; --apply merges them)"))


if __name__ == "__main__":
    main()

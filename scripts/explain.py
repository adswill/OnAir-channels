#!/usr/bin/env python3
"""Writes the comment for a refused submission: what is wrong, in plain words, and what to do. python3 scripts/explain.py result.json > comment.md"""
import json, sys

# (text found in the message, what to do); the first match wins
ADVICE = [
    ("latitude and longitude are empty", "A DAB transmitter needs the place where it stands. Click **Edit** on the first post of this issue, replace the empty `,,` after "
     "the MainId and SubId with the latitude and longitude (decimal degrees, a point not a comma, for example `51.50134,-0.14190`) and add the site name. "
     "Saving the edit checks it again. If you do not know the position, you can close this issue: the transmitter stays unlisted."),
    ("No ```csv block", "The text must contain the lines `mode:`, `country:`, `city:` and, under them, a block that starts with three backticks and `csv` and ends with three "
     "backticks. If you wrote a comment instead of sending a scan, please open a normal issue (without `[submit]` in the title). To send a scan, use the "
     "**Submit** button in OnAir after a scan."),
    ("is missing", "Add the missing line at the top of the issue text (for example `city: Berlin`), then save the edit."),
    ("is not in cities/", "Use a city from `cities/<country>.csv` of this repository, written exactly as it is there (with its accents). OnAir offers only "
     "these; pick the nearest one in the app, or edit the `city:` line here."),
    ("Unknown country", "Use the two-letter ISO code from `countries.csv` (`GB` for the United Kingdom, not `UK`; `GR` for Greece, not `EL`)."),
    ("Unknown mode", "The mode line must be one of the folder names of this repository (dvb-t, dab, fm, atsc, atsc3, isdb-t, dtmb, dab-tii)."),
    ("outside the", "That frequency cannot be a channel of this mode. Check that the mode line matches the scan, and the frequency is in MHz (88.5, not 88500)."),
    ("comma", "Numbers use a point (88.5), not a comma (88,5). A name that contains a comma must be inside double quotes."),
    ("e-mail address", "Submissions are public. Remove the personal data from the row and edit the issue."),
    ("control or invisible", "A name contains a character that cannot be seen (shown as <U+....> above). Delete that character or the whole name and edit the issue; "
     "a newer OnAir version cleans these before sending."),
    ("more than 5 submissions", "To keep the list clean an account can send at most 5 submissions a day. Please send the rest tomorrow."),
    ("already listed", "This transmitter is listed at a different place. If the list is wrong, say so in a new issue without `[submit]`, with a source."),
]


def comment(res):
    if res.get("ok"):
        return "Added: %s. Thank you." % res.get("message", "")
    msg = res.get("message", "unknown reason")
    out = ["This submission was **not added**.", "", "What is wrong: %s" % msg, ""]
    for key, advice in ADVICE:
        if key in msg:
            out += ["What to do: " + advice, ""]
            break
    else:
        out += ["What to do: compare the text with the example in the README (section 'How data gets in'), edit this issue and save; the checks run again on every edit.", ""]
    out += ["Nothing was written to the list. You can fix the text by editing the first post of this issue (the checks run again when you save), or send the scan again from OnAir. "
            "If you think the refusal is wrong, write a comment here and a person will look."]
    return "\n".join(out)


if __name__ == "__main__":
    print(comment(json.load(open(sys.argv[1], encoding="utf-8"))))

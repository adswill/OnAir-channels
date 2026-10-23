# OnAir channels

A shared list of which channels can be received where, collected by users of [OnAir](https://github.com/adswill/OnAir) from their own scans.
Use it to see what a city should offer and what your antenna is missing: OnAir's Scan tab has a **Shared data** view that reads these files.

## Layout

One folder per scan mode, one file per country inside:

| Folder | Mode |
|---|---|
| `dvb-t/` | DVB-T and DVB-T2 |
| `atsc/` | ATSC 1.0 |
| `atsc3/` | ATSC 3.0 |
| `isdb-t/` | ISDB-T |
| `dtmb/` | DTMB |
| `dab/` | DAB and DAB+ |
| `fm/` | FM radio |
| `dab-tii/` | DAB transmitter sites (see [DAB transmitters](#dab-transmitters-dab-tii)) |

`<mode>/<ISO2>.csv` (ISO 3166 alpha-2 country code, for example `dvb-t/DE.csv`). The first line is the header:

```
city,freq_mhz,bw_mhz,standard,network,services,snr_db,reports,first_seen,last_seen
```

| Column | Meaning |
|---|---|
| `city` | A name from `cities/<ISO2>.csv` |
| `freq_mhz`, `bw_mhz` | Centre frequency and channel width in MHz |
| `standard` | For example `DVB-T2`, `DVB-T`, `ATSC 3.0`, `DAB`, `FM` |
| `network` | Network name, or the DAB ensemble, or the FM station name |
| `services` | Service or station names joined with `\|` |
| `snr_db` | The best SNR anyone reported for this channel in this city |
| `reports` | How many submissions contained this channel |
| `first_seen`, `last_seen` | Dates (UTC, `YYYY-MM-DD`) of the first and the latest submission |

Plain CSV as in RFC 4180 (fields with a comma or quote are quoted), sorted by city, then frequency. Two entries of one city within 0.05 MHz are the
same channel.

`countries.csv` (`iso2,name`) and `cities/<ISO2>.csv` (`name,admin1,lat,lon,population`) list the places a submission can name. They are built
from GeoNames by `scripts/make_cities.py` (cities with at least 15000 inhabitants). `admin1` is the region (state, province, ...); the app
shows it after the name ("Palhoça, Santa Catarina"). A name must be unique per country, so a name that occurs twice carries its region itself
("São José, Santa Catarina") and its `admin1` stays empty; two equal names in one region add the position to the smaller one. The positions are
only there to tell cities apart; nothing a user sends contains a position. When the script renames a city it renames it in the channel files
too.

## DAB transmitters (`dab-tii/`)

OnAir reads the transmitter identification (TII, ETSI EN 300 401 clause 14.8) that DAB networks send: every transmitter of an ensemble has a
MainId (0-69) and a SubId (0-23). `dab-tii/<ISO2>.csv` says where each one stands, so OnAir's DAB **Map** tab can show the transmitters a
user receives on a map, with distance and bearing.

```
eid,main,sub,lat,lon,site,power_kw,channel_mhz,reports,first_seen,last_seen
```

| Column | Meaning |
|---|---|
| `eid` | The ensemble id, 4 hex digits (OnAir shows it in the Map tab) |
| `main`, `sub` | The TII MainId and SubId |
| `lat`, `lon` | The transmitter's position (degrees, WGS 84) |
| `site` | The site's name |
| `power_kw` | Radiated power in kW, if known (may be empty) |
| `channel_mhz` | The ensemble's frequency, if known (may be empty) |
| `reports`, `first_seen`, `last_seen` | How many submissions named this transmitter, and when |

A transmitter is identified by (`eid`, `main`, `sub`), sorted in that order. OnAir knows the ids from the air, but not where the transmitter
stands: when you submit one from the Map tab, the app fills in the ids and you add the position and the site's name (from your national
regulator's list, the operator, or the site itself). A submission of a transmitter already listed within 2 km of its position confirms it
(`reports` goes up, empty fields are filled); one that puts it more than 2 km elsewhere is refused, so that one wrong submission cannot move
a transmitter. If a listed position is wrong, open a normal issue (not a submission) and it is corrected by hand.

The submission text:

````
mode: dab-tii
country: GB

```csv
eid,main,sub,lat,lon,site,power_kw,channel_mhz
F0A1,3,12,52.10000,-1.20000,Example Hill,5,225.648
```
````

Checks: a known country, ids in range, a real position (not 0, 0), power 0 to 1000 kW, a channel in a DAB band, at most 100 transmitters, and the
same text rules as for channel names.

## How data gets in

1. In OnAir, finish a scan. The app asks whether you want to share it (you can say no, or never ask again).
2. Pick your country and the nearest city. The app shows you the exact text it will submit.
3. Your browser opens GitHub with a new issue filled in (`template=submit.yml`). Press **Submit new issue**.
4. A workflow (`.github/workflows/ingest.yml`, `scripts/ingest.py`) checks the text and merges it into the file of that mode and country:
   same city and frequency within 0.05 MHz raises `reports` by one, updates `last_seen`, keeps the best SNR and merges the service names; other
   channels are added. It commits the change with the issue number, comments and closes the issue.
   A submission that fails the checks gets a comment with the reason and the label `invalid`.

The checks (a refused submission can be fixed by editing the issue, see below): a known mode folder, a known country code, a city that is in `cities/<ISO2>.csv`, frequencies within the band of that mode, at most
300 rows, sane numbers (bandwidth 0 to 10 MHz, SNR -30 to 60 dB).

You can also open the issue by hand with the issue template. The text looks like this:

````
mode: dvb-t
country: DE
city: Berlin

```csv
freq_mhz,bw_mhz,standard,network,services,snr_db
522.0,8.0,DVB-T2,"Net, One",Das Erste|ZDF,17.2
```
````

## If your submission was refused

The bot answers every refused submission with a comment that says what is wrong and what to do, and adds the label `invalid`. Nothing is written
to the list in that case. In plain words:

1. Read the comment. It names the row and the problem.
2. Click the three dots (or the pencil) on the first post of your issue, choose **Edit**, fix the text and save. The checks run again when you
   save. If the text is now right, the data is added, the label goes away and the issue closes.
3. If you cannot fix it (for example you do not know where a DAB transmitter stands), close the issue. Nothing is lost.
4. If you think the refusal is wrong, write a comment. A person looks at it.

The usual reasons: a city that is not in `cities/<country>.csv` (the app offers only those; pick the nearest), a DAB transmitter without
latitude and longitude, a decimal comma (`88,5` instead of `88.5`) or a name with a comma that is not in double quotes, an invisible character in
a station name, a text that is not a scan at all (a question or a bug report: please open a normal issue without `[submit]` in the title), more
than 5 submissions in a day from one account.

Station names that repeat inside one channel, and `?` where a receiver could not read a name, are cleaned automatically; a national DAB
multiplex with 100 names is fine.

## Data quality

`python3 scripts/check_data.py` checks every data file (the workflow `check.yml` runs it on every change and once a week):

- errors, which fail the check: not UTF-8, wrong header or field count, rows not sorted (city, then frequency; DAB transmitters by ensemble id,
  MainId, SubId), two channels of one city within 0.05 MHz, a frequency outside the band of its mode, bandwidth or SNR that cannot be real, a city
  that is not in `cities/`, a date that is not a date, invisible characters, e-mail addresses, web addresses or phone numbers in a name;
- warnings, listed but not failing: a bandwidth that is unusual for the mode, `?` or repeated service names, and **stale rows**.

Stale policy: a channel or transmitter that was last reported more than 18 months ago is listed as a warning every week. Nothing is deleted
by a script: a person looks at the list, and a row that is still on the air is kept (a new report refreshes `last_seen`). `python3 scripts/tidy.py`
removes the `?` and repeated names from existing rows. `python3 scripts/reprocess.py` runs the current checks again on the refused submissions
and shows which would pass now (it changes nothing unless you pass `--apply`).

## Privacy

OnAir sends nothing by itself: no server, no key, no background upload. A submission contains only the mode, the country, the city and, for
each channel, frequency, bandwidth, standard, network name, service names and SNR. No position, no device or radio id, no app settings.
GitHub shows your GitHub user name on the issue, and issues and the history of the files are public and stay in the history of this
repository even if a row is later changed. Because of that the app tells you before it opens the browser.

## Tests

`python3 scripts/test_ingest.py` runs the ingest script on sample submissions (valid, invalid, merging) in a temporary copy of this folder, starting from empty data.

## Licence

- Submissions and the channel data: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/): by submitting you put the data in the public domain.
- Scripts: CC0 1.0 as well.
- `countries.csv` and `cities/`: from [GeoNames](https://www.geonames.org), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Attribution:
  "Data from GeoNames, https://www.geonames.org, CC BY 4.0". See `LICENSE-GeoNames`.

## Checks on every submission

Submissions never change the repository directly: the workflow runs this repository's own script on the issue text and only writes CSV rows that pass:

- known mode, country and city; frequencies inside the mode's band; at most 300 channels; finite numbers in sane ranges;
- standard names are plain (letters, digits, space, `. + / -`); names have length limits and may not contain control or invisible characters (bidi overrides, zero-width marks);
- a leading `=`, `+`, `-` or `@` is dropped from names, so a spreadsheet does not run them as formulas;
- no e-mail address, web address or phone number in a name (submissions are public);
- at most 5 submissions per GitHub account in 24 hours.

Every change is a commit that names its issue, so a wrong submission can be reverted.

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
from GeoNames by `scripts/make_cities.py` (cities with at least 15000 inhabitants). The positions are only there to tell cities apart; nothing a
user sends contains a position.

## How data gets in

1. In OnAir, finish a scan. The app asks whether you want to share it (you can say no, or never ask again).
2. Pick your country and the nearest city. The app shows you the exact text it will submit.
3. Your browser opens GitHub with a new issue filled in (`template=submit.yml`). Press **Submit new issue**.
4. A workflow (`.github/workflows/ingest.yml`, `scripts/ingest.py`) checks the text and merges it into the file of that mode and country:
   same city and frequency within 0.05 MHz raises `reports` by one, updates `last_seen`, keeps the best SNR and merges the service names; other
   channels are added. It commits the change with the issue number, comments and closes the issue.
   A submission that fails the checks gets a comment with the reason and the label `invalid`.

The checks: a known mode folder, a known country code, a city that is in `cities/<ISO2>.csv`, frequencies within the band of that mode, at most
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

## Privacy

OnAir sends nothing by itself: no server, no key, no background upload. A submission contains only the mode, the country, the city and, for
each channel, frequency, bandwidth, standard, network name, service names and SNR. No position, no device or radio id, no app settings.
GitHub shows your GitHub user name on the issue, and issues and the history of the files are public and stay in the history of this
repository even if a row is later changed. Because of that the app tells you before it opens the browser.

## Tests

`python3 scripts/test_ingest.py` runs the ingest script on sample submissions (valid, invalid, merging) in a temporary copy of this folder.

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
- at most 5 submissions per GitHub account in 24 hours.

Every change is a commit that names its issue, so a wrong submission can be reverted.

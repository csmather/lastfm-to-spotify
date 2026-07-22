# lastfm-to-spotify

Pulls all your Last.fm **loved tracks** and dumps them into one new Spotify playlist.

## Setup

```bash
cd ~/projects/random/lastfm-to-spotify
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your keys
```

### Spotify app redirect URI
In your Spotify app settings (https://developer.spotify.com/dashboard), add this
exact Redirect URI:

```
http://127.0.0.1:8888/callback
```

Spotify requires `127.0.0.1` (not `localhost`). It must match `SPOTIFY_REDIRECT_URI`
in `.env` character-for-character.

## Run

```bash
source .venv/bin/activate
python loved_to_spotify.py
```

First run opens a browser to authorize Spotify. After you approve, it redirects to
a `127.0.0.1:8888` URL that won't load anything — that's fine, just copy the full
URL from the address bar and paste it back into the terminal if prompted. The auth
token is cached in `.spotify_cache` so you only do this once.

Each Spotify search result is validated against the loved track's title and artist
(fuzzy match), because Spotify returns a best-effort hit for *anything* — so a track
that isn't on Spotify would otherwise get a wrong substitute. Results that don't
clear the confidence bar (`ACCEPT_SCORE`) are treated as "no match" and skipped. Two
lists print at the end:

- **low-confidence matches** — added, but shows what Spotify picked so you can eyeball it
- **no Spotify match** — skipped entirely (e.g. tracks genuinely not on Spotify)

### Filter by date loved
Make a playlist from only the tracks you loved in a date range:

```bash
python loved_to_spotify.py --since 2025-01-01
python loved_to_spotify.py --since 2025-01-01 --until 2025-06-30
python loved_to_spotify.py --since 2025-01-01 --name "Loved this year"
```

Dates are `YYYY-MM-DD` (interpreted as local midnight). When a range is given, it's
appended to the playlist name automatically so dated playlists stay distinct. Tracks
with no Last.fm "date loved" timestamp are skipped while filtering.

## How the match thresholds were tuned (`calibrate.py`)

The confidence thresholds in `loved_to_spotify.py` (`ACCEPT_SCORE = 0.75`,
`REVIEW_SCORE = 0.88`) aren't guesses — they were calibrated against a real loved
list. `calibrate.py` runs the actual matching pipeline but, instead of building a
playlist, dumps every track's best Spotify candidate with its separate title/artist
sub-scores to `scores.tsv`, sorted by blended score. Reading the low end of that file
is how the keep/skip line was chosen:

- every **wrong** match scored `<= 0.66` (same-title/wrong-artist, or same-artist/wrong-song)
- every **correct** match scored `>= 0.91`
- so `0.75` sits in the gap; the lone casualty is artist abbreviations (e.g. `TEED`
  for the full band name, ~0.60), which get skipped

It's kept in the repo for that reasoning trail, not as a feature you need to run. If
you ever want to re-check the distribution against your own library:

```bash
python calibrate.py        # uses the same .env; writes scores.tsv (gitignored)
```

It uses Spotify's client-credentials flow (app token, no browser login needed).

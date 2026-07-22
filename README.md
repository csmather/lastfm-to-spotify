# lastfm-to-spotify

Pulls a user's Last.fm **loved tracks** and dumps them into a new Spotify playlist.

## Setup

### 1. Clone and install

```bash
git clone https://github.com/csmather/lastfm-to-spotify && cd lastfm-to-spotify
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

You'll fill in `.env` with keys from the next two steps.

### 2. Get Last.fm API credentials

1. Create an API account at https://www.last.fm/api/account/create (log in first;
   the "callback URL" field can be left blank — this tool doesn't use it).
2. Copy the **API key** it gives you into `LASTFM_API_KEY` in `.env`.
3. Set `LASTFM_USER` to your **Last.fm username** (or the one whose loved tracks you want).

Your loved tracks are public, so no Last.fm login/authorization is needed at runtime.

### 3. Get Spotify API credentials

1. Go to the dashboard at https://developer.spotify.com/dashboard and **Create app**
   (any name/description; check the Web API box if asked).
2. From the app's **Settings**, copy the **Client ID** and **Client secret** into
   `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env`.
3. Add this exact **Redirect URI** and save:

   ```
   http://127.0.0.1:8888/callback
   ```

   Spotify requires `127.0.0.1` (not `localhost`), and it must match.
   Leave the default in `.env` as-is unless you change it here too.

## Run

```bash
source .venv/bin/activate
python loved_to_spotify.py
```

First run opens a browser to authorize Spotify.
The auth token is cached in `.spotify_cache` so you only do this once.

Each Spotify search result is validated against the loved track's title and artist
(fuzzy match), because Spotify returns a best-effort hit for *anything* — so a track
that isn't on Spotify would otherwise get a wrong substitute. Results that don't
clear the confidence bar (`ACCEPT_SCORE`) are treated as "no match" and skipped. Two
lists print at the end:

- **low-confidence matches** — added, but shows what Spotify picked so you can eyeball it
- **no Spotify match** — skipped entirely (e.g. tracks genuinely not on Spotify)

### Filter by date loved
To make a playlist from only the tracks you loved in a date range:

```bash
python loved_to_spotify.py --since 2025-01-01
python loved_to_spotify.py --since 2025-01-01 --until 2025-06-30
python loved_to_spotify.py --since 2025-01-01 --name "Loved this year"
```

Dates are `YYYY-MM-DD` (interpreted as local midnight). When a range is given, it's
appended to the playlist name automatically so dated playlists stay distinct. Tracks
with no Last.fm "date loved" timestamp are skipped while filtering.

## Track Matching Calibration (`calibrate.py`)

The confidence thresholds in `loved_to_spotify.py` (`ACCEPT_SCORE = 0.75`,
`REVIEW_SCORE = 0.88`) were calibrated against a real loved list.
`calibrate.py` runs the actual matching pipeline, but instead of building a
playlist, it dumps every track's best Spotify candidate with its separate title/artist
sub-scores to `scores.tsv`, sorted by blended score.

Reading the low end of that file is how the keep/skip line was chosen:

- every **wrong** match scored `<= 0.66` (same-title/wrong-artist, or same-artist/wrong-song)
- every **correct** match scored `>= 0.91`
- so `0.75` sits in the gap; the lone casualty is **artist abbreviations** (e.g. `TEED`
  on Spotfy vs. `Totally Enormous Extinct Dinosaurs` on Last.fm, ~0.60), which get skipped

It's kept in the repo for that reasoning trail, not as a feature you need to run.
If you ever want to re-check the distribution against your own library:

```bash
python calibrate.py        # uses the same .env; writes scores.tsv (gitignored)
```

It uses Spotify's client-credentials flow (app token, no browser login needed).

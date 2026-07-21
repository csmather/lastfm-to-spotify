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

Any tracks that don't match on Spotify get printed at the end.

## Later (not built yet)
Each track keeps its Last.fm "date loved" timestamp (`LovedTrack.uts`), so filtering
to "loved since <date>" into its own playlist is a small addition.

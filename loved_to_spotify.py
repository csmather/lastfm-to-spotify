#!/usr/bin/env python3
"""
Pull your Last.fm "loved tracks" and dump them all into one new Spotify playlist.

Minimal first build: grabs every loved track, matches each to a Spotify track,
creates a fresh playlist, and adds the matches. Unmatched tracks are printed at
the end so you can eyeball them.

The Last.fm 'date loved' timestamp is parsed and kept on each track (see
LovedTrack.uts) so a future "loved since <date>" filter is a one-liner — not
wired up yet, on purpose.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from typing import NoReturn

import requests
import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_USER = os.getenv("LASTFM_USER")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

PLAYLIST_NAME = os.getenv("PLAYLIST_NAME", "Last.fm Loved Tracks")

LASTFM_ROOT = "https://ws.audioscrobbler.com/2.0/"


@dataclass
class LovedTrack:
    name: str
    artist: str
    uts: int  # unix timestamp of when you loved it (0 if missing)


def die(msg: str) -> NoReturn:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_date(s: str) -> int:
    """Parse a YYYY-MM-DD date (local midnight) into a unix timestamp."""
    try:
        return int(datetime.strptime(s, "%Y-%m-%d").timestamp())
    except ValueError:
        die(f"bad date {s!r} — use YYYY-MM-DD")


def filter_by_date(
    tracks: list["LovedTrack"], since: int | None, until: int | None
) -> list["LovedTrack"]:
    """Keep tracks loved within [since, until]. Tracks with no date are dropped
    only when a bound is active (we can't place them on a timeline)."""
    if since is None and until is None:
        return tracks
    kept = []
    undated = 0
    for t in tracks:
        if not t.uts:
            undated += 1
            continue
        if since is not None and t.uts < since:
            continue
        if until is not None and t.uts > until:
            continue
        kept.append(t)
    if undated:
        print(f"  (skipped {undated} track(s) with no 'date loved' timestamp)")
    return kept


def check_config() -> None:
    missing = [
        k
        for k, v in {
            "LASTFM_API_KEY": LASTFM_API_KEY,
            "LASTFM_USER": LASTFM_USER,
            "SPOTIFY_CLIENT_ID": SPOTIFY_CLIENT_ID,
            "SPOTIFY_CLIENT_SECRET": SPOTIFY_CLIENT_SECRET,
        }.items()
        if not v
    ]
    if missing:
        die(f"missing env vars: {', '.join(missing)} (copy .env.example -> .env)")


def get_loved_tracks() -> list[LovedTrack]:
    """Page through user.getLovedTracks until we've got them all."""
    tracks: list[LovedTrack] = []
    page = 1
    total_pages = 1
    while page <= total_pages:
        resp = requests.get(
            LASTFM_ROOT,
            params={
                "method": "user.getLovedTracks",
                "user": LASTFM_USER,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": 200,
                "page": page,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            die(f"last.fm: {data.get('message', data['error'])}")

        loved = data.get("lovedtracks", {})
        attr = loved.get("@attr", {})
        total_pages = int(attr.get("totalPages", 1))

        for t in loved.get("track", []):
            tracks.append(
                LovedTrack(
                    name=t.get("name", ""),
                    artist=t.get("artist", {}).get("name", ""),
                    uts=int(t.get("date", {}).get("uts", 0)),
                )
            )
        print(f"  fetched page {page}/{total_pages} ({len(tracks)} tracks so far)")
        page += 1
        time.sleep(0.2)  # be polite
    return tracks


def spotify_client() -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope="playlist-modify-public playlist-modify-private",
        cache_path=".spotify_cache",
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def find_spotify_uri(sp: spotipy.Spotify, track: LovedTrack) -> str | None:
    """Search Spotify for a loved track; return the best-guess track URI."""
    # Field-scoped query first (most precise), then a loose fallback.
    for query in (
        f'track:"{track.name}" artist:"{track.artist}"',
        f"{track.name} {track.artist}",
    ):
        try:
            res = sp.search(q=query, type="track", limit=1)
        except spotipy.SpotifyException as e:
            print(f"  ! search failed for {track.artist} - {track.name}: {e}")
            return None
        items = res.get("tracks", {}).get("items", [])
        if items:
            return items[0]["uri"]
    return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Import Last.fm loved tracks into a new Spotify playlist."
    )
    p.add_argument(
        "--since",
        metavar="YYYY-MM-DD",
        help="only include tracks loved on/after this date",
    )
    p.add_argument(
        "--until",
        metavar="YYYY-MM-DD",
        help="only include tracks loved on/before this date",
    )
    p.add_argument(
        "--name",
        help="playlist name (default: PLAYLIST_NAME env, with date range appended)",
    )
    return p.parse_args()


def build_playlist_name(base: str, since: str | None, until: str | None) -> str:
    if since and until:
        return f"{base} ({since} to {until})"
    if since:
        return f"{base} (since {since})"
    if until:
        return f"{base} (until {until})"
    return base


def main() -> None:
    args = parse_args()
    check_config()

    since_ts = parse_date(args.since) if args.since else None
    until_ts = parse_date(args.until) if args.until else None
    if since_ts and until_ts and since_ts > until_ts:
        die("--since is after --until")

    print("Fetching loved tracks from Last.fm...")
    loved = get_loved_tracks()
    if not loved:
        die("no loved tracks found")
    print(f"Got {len(loved)} loved tracks.")

    loved = filter_by_date(loved, since_ts, until_ts)
    if not loved:
        die("no loved tracks in that date range")
    if since_ts or until_ts:
        print(f"{len(loved)} track(s) in range.")
    print()

    print("Authorizing with Spotify (a browser window may open)...")
    sp = spotify_client()
    me = sp.current_user()
    user_id = me["id"]
    print(f"Logged in as {me.get('display_name', user_id)}.\n")

    print("Matching tracks on Spotify...")
    uris: list[str] = []
    misses: list[LovedTrack] = []
    for i, t in enumerate(loved, 1):
        uri = find_spotify_uri(sp, t)
        if uri:
            uris.append(uri)
        else:
            misses.append(t)
        if i % 25 == 0 or i == len(loved):
            print(f"  matched {len(uris)}/{i} (checked {i}/{len(loved)})")

    if not uris:
        die("nothing matched on Spotify — check your keys / market")

    base_name = args.name or PLAYLIST_NAME
    playlist_name = build_playlist_name(base_name, args.since, args.until)
    desc = "Imported from Last.fm loved tracks"
    if args.since or args.until:
        desc += f" ({args.since or 'start'} to {args.until or 'now'})"

    print(f"\nCreating playlist '{playlist_name}'...")
    playlist = sp.user_playlist_create(
        user=user_id,
        name=playlist_name,
        public=False,
        description=desc,
    )
    playlist_id = playlist["id"]

    # Spotify caps adds at 100 URIs per request.
    for i in range(0, len(uris), 100):
        sp.playlist_add_items(playlist_id, uris[i : i + 100])
        print(f"  added {min(i + 100, len(uris))}/{len(uris)}")

    print(f"\nDone. Added {len(uris)} tracks to '{playlist_name}'.")
    print(f"Open it: {playlist['external_urls']['spotify']}")

    if misses:
        print(f"\n{len(misses)} track(s) had no Spotify match:")
        for t in misses:
            print(f"  - {t.artist} - {t.name}")


if __name__ == "__main__":
    main()

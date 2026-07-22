#!/usr/bin/env python3
"""
Threshold-calibration harness — NOT part of the tool, kept for context.

This is the one-off script used to pick the confidence thresholds in
loved_to_spotify.py (ACCEPT_SCORE / REVIEW_SCORE). It runs the *real* matching
pipeline against your live loved tracks, but instead of building a playlist it
dumps every track's best Spotify candidate with its separate title/artist
sub-scores to `scores.tsv`, sorted by blended score. Eyeballing that file is how
we found where correct vs. incorrect matches actually separate.

What the data showed (on a 225-track loved list, 2026-07-21):
  - Every WRONG match scored <= 0.66 blended:
      * same title, different artist  ("The Hooters - Until I Find You Again")
      * same artist, wrong song       ("Kadomatsu - Airport Lady" -> "Fly-By-Day")
  - Every CORRECT match scored >= 0.91 blended.
  - The lone exception was artist abbreviations ("TEED" for the full band name),
    correct but ~0.60 — indistinguishable from wrong matches by score alone, so
    accepted as a known casualty.
  => ACCEPT_SCORE = 0.75 sits in the clean 0.66–0.91 gap; REVIEW_SCORE = 0.88
     flags anything kept but not near-perfect.

It also surfaced a real bug: the old normalizer stripped all non-ASCII, so any two
non-Latin artist names collapsed to '' and scored a perfect 1.0 (this is why a
Japanese track mis-matched at 0.85). Fixed in loved_to_spotify._normalize.

Uses Spotify's client-credentials flow (app token, no user login) — needs the same
.env as the main tool. Run from the project dir:  python calibrate.py
"""

import csv
import os
import sys

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

import loved_to_spotify as m

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "scores.tsv")


def main() -> None:
    sp = spotipy.Spotify(
        auth_manager=SpotifyClientCredentials(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
        )
    )

    loved = m.get_loved_tracks()
    print(f"{len(loved)} loved tracks fetched", file=sys.stderr)

    rows = []
    for i, t in enumerate(loved, 1):
        candidates: dict[str, dict] = {}
        for q in (f'track:"{t.name}" artist:"{t.artist}"', f"{t.name} {t.artist}"):
            try:
                res = sp.search(q=q, type="track", limit=5)
            except spotipy.SpotifyException as e:
                print(f"  search err: {e}", file=sys.stderr)
                continue
            for it in res.get("tracks", {}).get("items", []):
                candidates[it["uri"]] = it

        if not candidates:
            rows.append((t.artist, t.name, "", "", 0.0, 0.0, 0.0))
            continue

        best = max(candidates.values(), key=lambda it: m._score_candidate(t, it))
        title_sim = m._sim(t.name, best.get("name", ""))
        artists = [a.get("name", "") for a in best.get("artists", [])]
        artist_sim = max((m._sim(t.artist, a) for a in artists), default=0.0)
        blend = 0.5 * title_sim + 0.5 * artist_sim
        rows.append(
            (
                t.artist,
                t.name,
                ", ".join(artists),
                best.get("name", ""),
                round(title_sim, 3),
                round(artist_sim, 3),
                round(blend, 3),
            )
        )
        if i % 25 == 0:
            print(f"  {i}/{len(loved)}", file=sys.stderr)

    rows.sort(key=lambda r: r[6])
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        w.writerow(
            ["loved_artist", "loved_title", "cand_artist", "cand_title",
             "title_sim", "artist_sim", "blend"]
        )
        w.writerows(rows)
    print(f"wrote {OUT}  (sorted by blend, ascending — read the low end)", file=sys.stderr)


if __name__ == "__main__":
    main()

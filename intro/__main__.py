"""Preview the smoke collage intro.

Examples:

    python -m intro --still preview.png --clip preview.mp4
    python -m intro --density 0.8 --drift 1.6 --tiles night-stadium,goal-posts,football
"""

from __future__ import annotations

import argparse
from pathlib import Path

from intro.smoke_collage import TILE_IDS, IntroConfig, write_clip, write_still


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render the picks intro: original football collage under drifting smoke.")
    parser.add_argument("--still", type=Path, required=True, help="PNG path for one frame")
    parser.add_argument("--clip", type=Path, help="Optional .mp4 or .gif of the smoke loop")
    parser.add_argument("--density", type=float, default=0.62, help="Smoke density from 0 (clear) to 1 (thick)")
    parser.add_argument("--drift", type=float, default=1.0, help="How far the smoke layers travel during the loop")
    parser.add_argument(
        "--tiles",
        default=",".join(TILE_IDS),
        help=f"Comma-separated collage tiles, back to front. Known: {', '.join(TILE_IDS)}",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--seconds", type=float, default=2.5)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--title", default="PICKS", help="Wordmark drawn through the smoke. Empty string hides it.")
    args = parser.parse_args(argv)
    tiles = tuple(part.strip() for part in args.tiles.split(",") if part.strip())
    config = IntroConfig(
        width=args.width,
        height=args.height,
        smoke_density=args.density,
        drift_speed=args.drift,
        tiles=tiles,
        seed=args.seed,
        fps=args.fps,
        seconds=args.seconds,
        title=args.title,
    )
    still = write_still(config, args.still)
    print(still)
    if args.clip:
        clip = write_clip(config, args.clip)
        print(clip)


if __name__ == "__main__":
    main()

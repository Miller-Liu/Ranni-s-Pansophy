"""Command line.

    ranni scan <image> [--debug]     one screenshot: tiles, selected relic, effects, score
    ranni run                        live overlay (Windows): Ctrl+Alt+Space on/off, Ctrl+Alt+End quit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from ranni.effects import EffectManager
from ranni.scoring import Scorer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ranni")
    parser.add_argument("--builds", type=Path, default=Path("settings/builds.json"))
    parser.add_argument("--effects", type=Path, default=Path("settings/effects.json"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("scan", help="scan one screenshot file")
    p.add_argument("image", type=Path)
    p.add_argument("--debug", action="store_true", help="save debug/<name>/scene.png with everything drawn")

    p = sub.add_parser("run", help="live overlay (Windows)")
    p.add_argument("--capture", choices=["auto", "dxcam", "mss"], default="auto")
    p.add_argument("--interval", type=float, default=0.25, help="seconds between scans while live")
    p.add_argument("--no-text-boxes", action="store_true", help="don't outline every line of text OCR found")

    args = parser.parse_args(argv)
    manager = EffectManager(args.effects)
    scorer = Scorer.load(args.builds) if args.builds.exists() else None
    if scorer is None:
        print(f"note: no builds loaded from {args.builds}; relics won't be scored")

    if args.cmd == "run":
        if sys.platform != "win32":
            raise SystemExit("`ranni run` needs Windows (screen capture, hotkeys and overlay are Windows-only)")
        from ranni.app import run

        run(manager, scorer, args.capture, args.interval, not args.no_text_boxes)
        return 0
    return _scan_file(args, manager, scorer)


def _scan_file(args, manager, scorer) -> int:
    from ranni.draw import draw_scene
    from ranni.ocr import default_engine
    from ranni.scan import scan, summary

    image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"cannot read {args.image} (use PNG/JPG/WebP)")
    engine = default_engine()
    if engine is None:
        print("note: no OCR on this platform (Windows only); finding tiles only")

    scene = scan(image, engine, manager, scorer)

    print(f"{len(scene.tiles)} tiles" + (f", selected: #{scene.selected}" if scene.selected is not None else ""))
    for i, (x, y, w, h) in enumerate(scene.tiles):
        print(f"  #{i:<2} x={x} y={y} size={w}" + ("   <- selected" if i == scene.selected else ""))
    if engine is not None:
        print(f"\ntext read ({len(scene.lines)} lines):")
        for line in scene.lines:
            print(f"  {line.text}")
        print(f"\neffects recognized ({len(scene.effects)}):")
        for e in scene.effects:
            pts = scene.score.points.get(e.text) if scene.score else None
            print(f"  {e.text}" + (f"   +{pts:g}" if pts is not None else ""))
        if scene.score is not None:
            print(f"\n{summary(scene.score)}")
    print("\n" + "  ".join(f"{k} {v:.0f}ms" for k, v in scene.timings.items()))

    if args.debug:
        out = Path("debug") / args.image.stem
        out.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out / "scene.png"), draw_scene(image, scene))
        print(f"debug image: {out / 'scene.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

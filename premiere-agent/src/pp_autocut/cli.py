"""커맨드라인 진입점.

사용 예:
    python -m pp_autocut input.mp4 -o cuts.json
    python -m pp_autocut input.mp4 --static-threshold 1.5 --min-static-sec 0.8
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .analyzer import analyze_motion
from .detector import build_result
from .exporter import write_json
from .models import DetectParams


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_params(args, config: dict) -> DetectParams:
    p = DetectParams(**{k: v for k, v in config.items() if k in DetectParams().to_dict()})
    if args.auto_threshold:
        p.auto_threshold = True
    if args.static_threshold is not None:
        p.static_threshold = args.static_threshold
    if args.min_static_sec is not None:
        p.min_static_sec = args.min_static_sec
    if args.min_freeze_sec is not None:
        p.min_freeze_sec = args.min_freeze_sec
    if args.pad_frames is not None:
        p.pad_frames = args.pad_frames
    if args.downscale_width is not None:
        p.downscale_width = args.downscale_width
    return p


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pp_autocut",
        description="영상에서 정지/버벅 구간을 검출해 프리미어 컷 계획(JSON)을 만든다.",
    )
    parser.add_argument("input", help="입력 영상 파일 경로")
    parser.add_argument("-o", "--out", default=None, help="결과 JSON 경로 (기본: <입력>.cuts.json)")
    parser.add_argument("-c", "--config", default=None, help="파라미터 JSON 설정 파일")
    parser.add_argument(
        "--auto-threshold",
        action="store_true",
        help="영상의 모션 분포로 정지 임계값을 자동 산출 (피사체 크기에 강건)",
    )
    parser.add_argument("--static-threshold", type=float, default=None)
    parser.add_argument("--min-static-sec", type=float, default=None)
    parser.add_argument("--min-freeze-sec", type=float, default=None)
    parser.add_argument("--pad-frames", type=int, default=None)
    parser.add_argument("--downscale-width", type=int, default=None)
    parser.add_argument("-q", "--quiet", action="store_true", help="요약 출력 생략")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.input):
        parser.error(f"입력 파일을 찾을 수 없습니다: {args.input}")

    params = build_params(args, _load_config(args.config))
    out_path = args.out or (os.path.splitext(args.input)[0] + ".cuts.json")

    motion, fps, frame_count, width, height = analyze_motion(
        args.input, downscale_width=params.downscale_width
    )
    result = build_result(args.input, motion, fps, frame_count, width, height, params)
    data = write_json(result, out_path)

    if not args.quiet:
        s = data["summary"]
        print(f"[pp_autocut] {args.input}")
        print(f"  해상도 {width}x{height} | {fps:.2f}fps | {frame_count}프레임 "
              f"({data['duration_sec']:.1f}s)")
        print(f"  제거 구간 {s['remove_count']}개 | {s['removed_frames']}프레임 "
              f"({s['removed_sec']:.1f}s) 컷")
        print(f"  -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

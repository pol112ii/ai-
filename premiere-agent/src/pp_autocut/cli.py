"""커맨드라인 진입점.

사용 예:
    python -m pp_autocut input.mp4 -o cuts.json
    python -m pp_autocut input.mp4 --auto-threshold
    python -m pp_autocut input.mp4 --static-mode mark --stutter-mode cut
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .analyzer import analyze
from .detector import build_result
from .exporter import write_json
from .models import DetectParams
from .preview import calibrate, print_calibration, render_preview, write_metrics_csv

MODES = ("cut", "mark", "off")


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_params(args, config: dict) -> DetectParams:
    valid = DetectParams().to_dict()
    p = DetectParams(**{k: v for k, v in config.items() if k in valid})
    if args.auto_threshold:
        p.auto_threshold = True
    for attr in (
        "static_threshold", "min_static_sec", "min_freeze_sec", "pad_frames",
        "downscale_width", "static_mode", "stutter_mode", "offcenter_mode",
        "min_offcenter_sec", "center_dist_thresh",
    ):
        val = getattr(args, attr, None)
        if val is not None:
            setattr(p, attr, val)
    return p


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="pp_autocut",
        description="영상에서 정지/버벅/오프센터 구간을 검출해 프리미어 컷·마커 계획(JSON)을 만든다.",
    )
    parser.add_argument("input", help="입력 영상 파일 경로")
    parser.add_argument("-o", "--out", default=None, help="결과 JSON 경로 (기본: <입력>.cuts.json)")
    parser.add_argument("-c", "--config", default=None, help="파라미터 JSON 설정 파일")
    parser.add_argument(
        "--auto-threshold", action="store_true",
        help="영상의 모션 분포로 정지 임계값을 자동 산출 (피사체 크기에 강건)",
    )
    parser.add_argument("--static-threshold", type=float, default=None)
    parser.add_argument("--min-static-sec", type=float, default=None)
    parser.add_argument("--min-freeze-sec", type=float, default=None)
    parser.add_argument("--pad-frames", type=int, default=None)
    parser.add_argument("--downscale-width", type=int, default=None)
    # 유형별 처리 방식: cut(잘라냄) / mark(표시만) / off(무시)
    parser.add_argument("--static-mode", choices=MODES, default=None, help="정지 구간 처리 (기본 mark)")
    parser.add_argument("--stutter-mode", choices=MODES, default=None, help="버벅임 처리 (기본 cut)")
    parser.add_argument("--offcenter-mode", choices=MODES, default=None, help="오프센터 처리 (기본 mark)")
    parser.add_argument("--min-offcenter-sec", type=float, default=None)
    parser.add_argument("--center-dist-thresh", type=float, default=None)
    # 진단/튜닝 도구
    parser.add_argument("--preview", metavar="OUT.mp4", default=None,
                        help="검출 결과를 오버레이한 미리보기 영상 생성")
    parser.add_argument("--metrics-csv", metavar="OUT.csv", default=None,
                        help="프레임별 지표 CSV 저장")
    parser.add_argument("--calibrate", action="store_true",
                        help="모션 분포에서 임계값 추천값 출력")
    parser.add_argument("-q", "--quiet", action="store_true", help="요약 출력 생략")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.input):
        parser.error(f"입력 파일을 찾을 수 없습니다: {args.input}")

    params = build_params(args, _load_config(args.config))
    out_path = args.out or (os.path.splitext(args.input)[0] + ".cuts.json")

    track = analyze(
        args.input, downscale_width=params.downscale_width, safe_zone=params.safe_zone
    )
    result = build_result(args.input, track, params)
    data = write_json(result, out_path)

    if args.calibrate:
        print_calibration(calibrate(track, params))
    if args.metrics_csv:
        write_metrics_csv(track, result, args.metrics_csv)
    if args.preview:
        render_preview(args.input, track, result, args.preview)

    if not args.quiet:
        s = data["summary"]
        print(f"[pp_autocut] {args.input}")
        print(f"  해상도 {track.width}x{track.height} | {track.fps:.2f}fps | "
              f"{track.frame_count}프레임 ({data['duration_sec']:.1f}s)")
        print(f"  ✂️  컷 {s['remove_count']}개 | {s['removed_frames']}프레임 ({s['removed_sec']:.1f}s)")
        reasons = ", ".join(f"{k} {v}" for k, v in s["mark_by_reason"].items()) or "-"
        print(f"  🔖 표시 {s['mark_count']}개 ({reasons})")
        print(f"  -> {out_path}")
        if args.preview:
            print(f"  🎬 미리보기 -> {args.preview}")
        if args.metrics_csv:
            print(f"  📊 지표 CSV -> {args.metrics_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

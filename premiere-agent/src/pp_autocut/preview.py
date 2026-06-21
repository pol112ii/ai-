"""검출 결과를 '눈으로' 확인하기 위한 진단 도구.

세 가지를 제공한다.
  1) render_preview : 원본 위에 안전영역/무게중심/모션점수/검출라벨을 입힌 미리보기 영상
  2) write_metrics_csv : 프레임별 지표(motion, cx, cy, border_ratio, label) CSV
  3) calibrate : 모션 분포에서 임계값 추천값 산출

오버레이 글자는 OpenCV 기본 폰트가 한글을 못 그리므로 영문 라벨을 쓴다.
  STATIC=정지, OFF-CENTER=중앙 피사체 빠짐(구도), STUTTER=버벅임
"""

from __future__ import annotations

import csv
from typing import Dict, List, Optional, Tuple

from .models import AnalysisResult, DetectParams, MotionTrack

try:
    import cv2
except ImportError as exc:  # pragma: no cover
    raise ImportError("opencv가 필요합니다. `pip install -r requirements.txt`") from exc

# 사유 -> (라벨, BGR 색)
_REASON_STYLE = {
    "static": ("STATIC", (0, 215, 255)),       # 노랑
    "offcenter": ("OFF-CENTER", (0, 0, 255)),  # 빨강
    "stutter": ("STUTTER", (255, 255, 0)),     # 하늘
}


def _label_per_frame(result: AnalysisResult) -> List[Optional[Tuple[str, str]]]:
    """프레임 -> (kind, reason). kind 는 'cut' 또는 'mark'. 없으면 None."""
    n = result.frame_count
    labels: List[Optional[Tuple[str, str]]] = [None] * n
    for seg in result.remove_segments:
        for i in range(seg.start_frame, min(seg.end_frame, n)):
            labels[i] = ("cut", seg.reason)
    for m in result.marks:  # 표시는 컷 위에 덮어쓰지 않고, 빈 곳에만
        for i in range(m.start_frame, min(m.end_frame, n)):
            if labels[i] is None:
                labels[i] = ("mark", m.reason)
    return labels


def render_preview(
    video_path: str, track: MotionTrack, result: AnalysisResult, out_path: str
) -> str:
    """검출 결과를 오버레이한 미리보기 영상을 만든다."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {video_path}")

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = track.fps
    vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))

    labels = _label_per_frame(result)
    margin = (1.0 - result.params.safe_zone) / 2.0
    sx0, sy0 = int(W * margin), int(H * margin)
    sx1, sy1 = int(W * (1 - margin)), int(H * (1 - margin))

    i = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok or i >= track.frame_count:
                break

            # 안전영역 박스(초록)
            cv2.rectangle(frame, (sx0, sy0), (sx1, sy1), (0, 200, 0), 1)

            # 내용(엣지) 무게중심 점 = 작업물·도구 위치
            cx = int(track.cx[i] * W)
            cy = int(track.cy[i] * H)
            cv2.circle(frame, (cx, cy), 7, (255, 255, 255), -1)
            cv2.circle(frame, (cx, cy), 8, (0, 0, 0), 1)

            # 상단 정보 바
            cv2.rectangle(frame, (0, 0), (W, 26), (0, 0, 0), -1)
            info = (f"f{i}  motion {track.motion[i]:4.1f}  "
                    f"center {track.center_ratio[i]:.2f}")
            cv2.putText(frame, info, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)

            # 검출 라벨 + 테두리
            lab = labels[i]
            if lab is not None:
                kind, reason = lab
                text, color = _REASON_STYLE.get(reason, (reason.upper(), (0, 255, 0)))
                tag = f"[{ 'CUT' if kind == 'cut' else 'MARK' }] {text}"
                cv2.rectangle(frame, (0, 0), (W - 1, H - 1), color, 6)
                cv2.putText(frame, tag, (6, H - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            color, 2, cv2.LINE_AA)

            vw.write(frame)
            i += 1
    finally:
        cap.release()
        vw.release()
    return out_path


def write_metrics_csv(track: MotionTrack, result: AnalysisResult, out_path: str) -> str:
    labels = _label_per_frame(result)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["frame", "sec", "motion", "cx", "cy", "center_ratio", "kind", "reason"])
        for i in range(track.frame_count):
            lab = labels[i] or ("", "")
            w.writerow([
                i, round(i / track.fps, 3), round(track.motion[i], 3),
                round(track.cx[i], 3), round(track.cy[i], 3),
                round(track.center_ratio[i], 3), lab[0], lab[1],
            ])
    return out_path


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    rank = (p / 100.0) * (len(sorted_vals) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (rank - lo)


def calibrate(track: MotionTrack, params: DetectParams) -> Dict:
    """모션/공간 분포를 보고 임계값 추천값을 산출한다."""
    motion = sorted(track.motion[1:]) if track.frame_count > 1 else [0.0]
    pcts = {f"p{p}": round(_percentile(motion, p), 3) for p in (50, 75, 90, 95, 99)}

    # static_threshold 후보: 상위 분위수의 일부 (auto 산출과 동일 로직)
    suggested_static = round(
        max(params.auto_floor, _percentile(motion, params.auto_percentile) * params.auto_ratio), 3
    )
    below = sum(1 for m in track.motion if m < suggested_static)

    # 중앙 안전영역 엣지 비율 분포 (작업 중인 프레임 기준)
    center = sorted(
        track.center_ratio[i]
        for i in range(track.frame_count)
        if track.motion[i] >= suggested_static
    )
    active_n = len(center)

    return {
        "frames": track.frame_count,
        "fps": round(track.fps, 3),
        "motion_percentiles": pcts,
        "suggested_static_threshold": suggested_static,
        "frames_below_suggested": below,
        "ratio_below_suggested": round(below / max(1, track.frame_count), 3),
        "active_frames": active_n,
        "center_ratio_p10": round(_percentile(center, 10), 3),
        "center_ratio_p25": round(_percentile(center, 25), 3),
        "center_ratio_p50": round(_percentile(center, 50), 3),
    }


def print_calibration(report: Dict) -> None:
    print("[calibrate] 분포 기반 추천")
    print(f"  프레임 {report['frames']} @ {report['fps']}fps")
    mp = report["motion_percentiles"]
    print(f"  모션 분위수: p50 {mp['p50']} | p75 {mp['p75']} | p90 {mp['p90']} | "
          f"p95 {mp['p95']} | p99 {mp['p99']}")
    print(f"  추천 static_threshold = {report['suggested_static_threshold']} "
          f"(이 값 미만 프레임 {report['ratio_below_suggested']*100:.0f}%)")
    print(f"  작업 중 프레임 {report['active_frames']}개의 중앙 엣지비율: "
          f"p10 {report['center_ratio_p10']} / p25 {report['center_ratio_p25']} / "
          f"p50 {report['center_ratio_p50']}")
    print(f"  -> center_content_thresh 는 보통 위 p10~p25 부근에서 잡는다 "
          f"(낮을수록 덜 민감).")

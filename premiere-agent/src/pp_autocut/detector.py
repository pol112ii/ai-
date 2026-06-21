"""모션 특징에서 정지/버벅/오프센터 구간을 검출한다.

이 모듈은 OpenCV에 의존하지 않는다(순수 파이썬). 합성 데이터로 독립 테스트 가능.

검출 규칙
---------
정지/버벅 (모션 점수 기반)
  1) 모션 점수가 static_threshold 미만인 프레임을 '저모션'으로 본다.
  2) 연속 저모션을 묶어 run 으로 만든다.
  3) run 길이로 분류:
       static_cut_sec 이상  -> "static" 컷  (확실한 데드 구간)
       static_mark_sec 이상 -> "static" 표시 (사람이 검수)
       min_freeze_sec 이상   -> "stutter" (잠깐 얼어붙는 버벅임)
       그보다 짧으면          -> 무시
오프센터 (구도/내용 기반)
  - 손 위치가 아니라 '중앙에 작업물·도구가 잘 보이나'를 본다.
  - '작업 중인데(움직임 있음)' 중앙 안전영역의 엣지 비율(center_ratio)이
    center_content_thresh 미만이면 '중앙 피사체 빠짐'으로 본다 -> "offcenter".

각 유형은 mode 에 따라 처리된다.
  cut  -> 실제로 잘라냄(remove)
  mark -> 자르지 않고 표시만(mark)
  off  -> 검출 안 함
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .models import AnalysisResult, DetectParams, MotionTrack, Segment


def compute_auto_threshold(motion: Sequence[float], params: DetectParams) -> float:
    """영상의 모션 분포에서 정지 임계값을 산출한다."""
    data = list(motion[1:]) if len(motion) > 1 else list(motion)
    if not data:
        return params.auto_floor
    data.sort()
    rank = (params.auto_percentile / 100.0) * (len(data) - 1)
    lo = int(rank)
    frac = rank - lo
    hi = min(lo + 1, len(data) - 1)
    pct = data[lo] + (data[hi] - data[lo]) * frac
    return max(params.auto_floor, pct * params.auto_ratio)


def _find_runs(flags: Sequence[bool]) -> List[Tuple[int, int]]:
    """True 가 연속된 구간 [start, end) 목록."""
    runs: List[Tuple[int, int]] = []
    start = None
    for i, f in enumerate(flags):
        if f:
            if start is None:
                start = i
        elif start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(flags)))
    return runs


def _find_low_runs(motion: Sequence[float], threshold: float) -> List[Tuple[int, int]]:
    return _find_runs([m < threshold for m in motion])


def _apply_pad(start: int, end: int, pad: int) -> Tuple[int, int] | None:
    s, e = start + pad, end - pad
    return (s, e) if e - s > 0 else None


def _mode_type(mode: str) -> str | None:
    """mode -> Segment.type. off 면 None(검출 제외)."""
    return {"cut": "remove", "mark": "mark"}.get(mode)


def detect_motion_segments(
    motion: Sequence[float], fps: float, params: DetectParams
) -> List[Segment]:
    """정지/버벅 구간을 검출해 remove 또는 mark 세그먼트로 반환(분류 전).

    정지는 길이에 따라: static_cut_sec 이상 컷, static_mark_sec 이상 표시.
    """
    if not motion:
        return []
    if params.auto_threshold:
        params.static_threshold = compute_auto_threshold(motion, params)

    static_cut = max(1, int(round(params.static_cut_sec * fps)))
    static_mark = max(1, int(round(params.static_mark_sec * fps)))
    min_freeze = max(1, int(round(params.min_freeze_sec * fps)))
    pad = max(0, int(params.pad_frames))

    out: List[Segment] = []
    for start, end in _find_low_runs(motion, params.static_threshold):
        length = end - start
        if length >= static_cut:
            reason, seg_type = "static", "remove"
        elif length >= static_mark:
            reason, seg_type = "static", "mark"
        elif length >= min_freeze:
            reason, seg_type = "stutter", _mode_type(params.stutter_mode)
        else:
            continue
        if seg_type is None:
            continue
        padded = _apply_pad(start, end, pad)
        if padded is None:
            continue
        out.append(Segment(type=seg_type, start_frame=padded[0], end_frame=padded[1], reason=reason))
    return out


def detect_offcenter(track: MotionTrack, params: DetectParams) -> List[Segment]:
    """중앙에 작업물·도구가 잘 안 보이는(중앙 피사체 빠짐) 구간을 검출.

    손 위치가 아니라 중앙 안전영역의 엣지 비율(center_ratio)로 판단한다.
    """
    if params.offcenter_mode == "off":
        return []
    seg_type = _mode_type(params.offcenter_mode)
    if seg_type is None:
        return []

    flags: List[bool] = []
    for i in range(track.frame_count):
        active = (not params.offcenter_requires_motion) or track.motion[i] >= params.static_threshold
        center_empty = track.center_ratio[i] < params.center_content_thresh
        flags.append(active and center_empty)

    min_off = max(1, int(round(params.min_offcenter_sec * track.fps)))
    pad = max(0, int(params.pad_frames))
    out: List[Segment] = []
    for start, end in _find_runs(flags):
        if end - start < min_off:
            continue
        padded = _apply_pad(start, end, pad)
        if padded is None:
            continue
        out.append(Segment(type=seg_type, start_frame=padded[0], end_frame=padded[1], reason="offcenter"))
    return out


def _fill_keeps(removes: List[Segment], n: int) -> List[Segment]:
    """remove 구간 사이를 keep 으로 채워 컷 타임라인을 구성한다."""
    removes = sorted(removes, key=lambda s: s.start_frame)
    segments: List[Segment] = []
    cursor = 0
    for r in removes:
        if r.start_frame > cursor:
            segments.append(Segment(type="keep", start_frame=cursor, end_frame=r.start_frame))
        segments.append(r)
        cursor = max(cursor, r.end_frame)
    if cursor < n:
        segments.append(Segment(type="keep", start_frame=cursor, end_frame=n))
    return segments


def build_result(source: str, track: MotionTrack, params: DetectParams) -> AnalysisResult:
    """MotionTrack -> 컷 타임라인(segments) + 표시(marks) 가 담긴 결과."""
    detections = detect_motion_segments(track.motion, track.fps, params)
    detections += detect_offcenter(track, params)

    removes = [s for s in detections if s.type == "remove"]
    marks = [s for s in detections if s.type == "mark"]
    marks.sort(key=lambda s: s.start_frame)

    return AnalysisResult(
        source=source,
        fps=track.fps,
        frame_count=track.frame_count,
        width=track.width,
        height=track.height,
        params=params,
        segments=_fill_keeps(removes, track.frame_count),
        marks=marks,
    )


# 하위 호환: 모션 배열만으로 keep/remove 타임라인을 얻는 헬퍼.
def detect_segments(motion: Sequence[float], fps: float, params: DetectParams) -> List[Segment]:
    detections = detect_motion_segments(motion, fps, params)
    removes = [s for s in detections if s.type == "remove"]
    return _fill_keeps(removes, len(motion))

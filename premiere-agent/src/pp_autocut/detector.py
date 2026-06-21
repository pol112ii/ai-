"""모션 점수 배열에서 정지/버벅 구간을 검출해 keep/remove 세그먼트로 만든다.

이 모듈은 OpenCV에 의존하지 않는다(순수 파이썬/넘파이). 따라서 합성 데이터로
독립 테스트가 가능하다.

검출 규칙
---------
1) 모션 점수가 static_threshold 미만인 프레임을 '저모션'으로 본다.
2) 연속한 저모션 프레임을 묶어 run 으로 만든다.
3) run 길이로 분류한다.
   - min_static_sec 이상  -> reason="static" (정지 장면, 컷 대상)
   - min_freeze_sec 이상   -> reason="stutter" (움직이다 잠깐 얼어붙는 버벅임, 컷 대상)
   - 그보다 짧으면          -> 무시(자연스러운 멈칫은 남긴다)
4) 컷 구간 앞뒤에 pad_frames 만큼 핸들을 남겨 너무 빡빡하게 자르지 않는다.
   핸들을 적용한 뒤 남는 길이가 없으면 그 컷은 버린다.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from .models import AnalysisResult, DetectParams, Segment


def compute_auto_threshold(motion: Sequence[float], params: DetectParams) -> float:
    """영상의 모션 분포에서 정지 임계값을 산출한다.

    움직이는 프레임들이 분포의 상위에 모이므로, 상위 분위수의 일부를
    임계값으로 삼으면 '거의 정지'와 '움직임'을 분리할 수 있다.
    """
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


def _find_low_runs(
    motion: Sequence[float], threshold: float
) -> List[Tuple[int, int]]:
    """모션 < threshold 인 연속 구간 [start, end) 목록을 반환."""
    runs: List[Tuple[int, int]] = []
    start = None
    for i, m in enumerate(motion):
        if m < threshold:
            if start is None:
                start = i
        else:
            if start is not None:
                runs.append((start, i))
                start = None
    if start is not None:
        runs.append((start, len(motion)))
    return runs


def detect_segments(
    motion: Sequence[float], fps: float, params: DetectParams
) -> List[Segment]:
    """모션 배열 -> keep/remove 세그먼트 리스트(타임라인 전체를 빈틈없이 덮는다)."""
    n = len(motion)
    if n == 0:
        return []

    if params.auto_threshold:
        # 실제 사용된 값을 출력에 반영하기 위해 params 에 기록한다.
        params.static_threshold = compute_auto_threshold(motion, params)

    min_static_frames = max(1, int(round(params.min_static_sec * fps)))
    min_freeze_frames = max(1, int(round(params.min_freeze_sec * fps)))
    pad = max(0, int(params.pad_frames))

    removes: List[Segment] = []
    for start, end in _find_low_runs(motion, params.static_threshold):
        length = end - start
        if length >= min_static_frames:
            reason = "static"
        elif length >= min_freeze_frames:
            reason = "stutter"
        else:
            continue  # 너무 짧은 멈칫은 남긴다

        # 앞뒤 핸들 적용
        s = start + pad
        e = end - pad
        if e - s <= 0:
            continue
        removes.append(Segment(type="remove", start_frame=s, end_frame=e, reason=reason))

    return _fill_keeps(removes, n)


def _fill_keeps(removes: List[Segment], n: int) -> List[Segment]:
    """remove 구간 사이를 keep 구간으로 채워 전체 타임라인을 구성한다."""
    removes = sorted(removes, key=lambda s: s.start_frame)
    segments: List[Segment] = []
    cursor = 0
    for r in removes:
        if r.start_frame > cursor:
            segments.append(Segment(type="keep", start_frame=cursor, end_frame=r.start_frame))
        segments.append(r)
        cursor = r.end_frame
    if cursor < n:
        segments.append(Segment(type="keep", start_frame=cursor, end_frame=n))
    return segments


def build_result(
    source: str,
    motion: Sequence[float],
    fps: float,
    frame_count: int,
    width: int,
    height: int,
    params: DetectParams,
) -> AnalysisResult:
    segments = detect_segments(motion, fps, params)
    return AnalysisResult(
        source=source,
        fps=fps,
        frame_count=frame_count,
        width=width,
        height=height,
        params=params,
        segments=segments,
    )

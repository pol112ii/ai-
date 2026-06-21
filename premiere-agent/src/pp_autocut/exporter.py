"""분석 결과를 프리미어 CEP/ExtendScript 패널이 읽을 JSON으로 내보낸다.

스키마: pp-autocut/v2
패널이 할 일
  1) cut_points 의 프레임 위치에서 시퀀스를 면도날(razor)로 자른다.
  2) remove_ranges 구간을 (뒤에서 앞 순서로) 리플 삭제한다.
  3) markers 의 각 구간/지점에 프리미어 마커를 찍어 사람이 검수하게 한다.
     (자르지 않고 '표시'만 하는 항목 — 정지/오프센터 등)
프레임 번호가 1차 기준이며, 초/타임코드는 참고용이다.
"""

from __future__ import annotations

import json
from typing import List

from .models import AnalysisResult, Segment
from .timecode import frames_to_seconds, frames_to_timecode

# 검출 사유별 마커 색상(프리미어 마커 색 이름)과 한글 라벨.
REASON_META = {
    "static": ("Yellow", "정지(움직임 없음)"),
    "offcenter": ("Red", "중앙 피사체 빠짐(구도 점검)"),
    "stutter": ("Cyan", "버벅임(프리즈/중복 프레임)"),
}


def _seg_dict(seg: Segment, fps: float) -> dict:
    d = {
        "type": seg.type,
        "reason": seg.reason,
        "start_frame": seg.start_frame,
        "end_frame": seg.end_frame,
        "start_sec": round(frames_to_seconds(seg.start_frame, fps), 3),
        "end_sec": round(frames_to_seconds(seg.end_frame, fps), 3),
        "start_tc": frames_to_timecode(seg.start_frame, fps),
        "end_tc": frames_to_timecode(seg.end_frame, fps),
    }
    return d


def _marker_dict(seg: Segment, fps: float) -> dict:
    color, label = REASON_META.get(seg.reason, ("Green", seg.reason))
    dur = round(seg.length_sec(fps), 2)
    d = _seg_dict(seg, fps)
    d.update({
        "color": color,
        "name": label,
        "comment": f"{label} · {dur}s",
    })
    return d


def to_dict(result: AnalysisResult) -> dict:
    fps = result.fps
    removes = result.remove_segments

    cut_set = set()
    for r in removes:
        cut_set.add(r.start_frame)
        cut_set.add(r.end_frame)
    cut_set.discard(0)
    cut_set.discard(result.frame_count)
    cut_points: List[int] = sorted(cut_set)

    # 마커 사유별 개수
    mark_by_reason: dict = {}
    for m in result.marks:
        mark_by_reason[m.reason] = mark_by_reason.get(m.reason, 0) + 1

    return {
        "schema": "pp-autocut/v2",
        "source": result.source,
        "fps": round(fps, 4),
        "frame_count": result.frame_count,
        "duration_sec": round(frames_to_seconds(result.frame_count, fps), 3),
        "resolution": {"width": result.width, "height": result.height},
        "params": result.params.to_dict(),
        "summary": {
            "remove_count": len(removes),
            "removed_frames": result.removed_frames,
            "removed_sec": round(frames_to_seconds(result.removed_frames, fps), 3),
            "mark_count": len(result.marks),
            "mark_by_reason": mark_by_reason,
        },
        "cut_points": cut_points,
        "remove_ranges": [_seg_dict(r, fps) for r in removes],
        "markers": [_marker_dict(m, fps) for m in result.marks],
        "segments": [_seg_dict(s, fps) for s in result.segments],
    }


def write_json(result: AnalysisResult, out_path: str) -> dict:
    data = to_dict(result)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

"""분석 결과를 프리미어 CEP/ExtendScript 패널이 읽을 JSON으로 내보낸다.

스키마: pp-autocut/v1
패널은 다음을 수행하면 된다.
  1) cut_points 의 각 프레임 위치에서 시퀀스를 면도날(razor)로 자른다.
  2) remove_ranges 의 각 구간을 리플 삭제(ripple delete)한다.
프레임 번호가 1차 기준이며, 초/타임코드는 참고용이다.
"""

from __future__ import annotations

import json
from typing import List

from .models import AnalysisResult
from .timecode import frames_to_seconds, frames_to_timecode


def to_dict(result: AnalysisResult) -> dict:
    fps = result.fps

    def seg_dict(seg) -> dict:
        d = {
            "type": seg.type,
            "start_frame": seg.start_frame,
            "end_frame": seg.end_frame,
            "start_sec": round(frames_to_seconds(seg.start_frame, fps), 3),
            "end_sec": round(frames_to_seconds(seg.end_frame, fps), 3),
            "start_tc": frames_to_timecode(seg.start_frame, fps),
            "end_tc": frames_to_timecode(seg.end_frame, fps),
        }
        if seg.reason:
            d["reason"] = seg.reason
        return d

    removes = result.remove_segments

    # 컷 지점: 각 remove 구간의 시작/끝 경계(중복 제거, 0과 끝은 제외).
    cut_set = set()
    for r in removes:
        cut_set.add(r.start_frame)
        cut_set.add(r.end_frame)
    cut_set.discard(0)
    cut_set.discard(result.frame_count)
    cut_points: List[int] = sorted(cut_set)

    return {
        "schema": "pp-autocut/v1",
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
        },
        "cut_points": cut_points,
        "remove_ranges": [seg_dict(r) for r in removes],
        "segments": [seg_dict(s) for s in result.segments],
    }


def write_json(result: AnalysisResult, out_path: str) -> dict:
    data = to_dict(result)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data

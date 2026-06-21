"""검출 로직 단위 테스트 (OpenCV 불필요, 합성 모션 데이터 사용)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pp_autocut.detector import (  # noqa: E402
    detect_segments,
    detect_motion_segments,
    detect_offcenter,
    _find_low_runs,
    compute_auto_threshold,
)
from pp_autocut.models import DetectParams, MotionTrack  # noqa: E402


def test_find_low_runs_basic():
    motion = [5, 5, 0, 0, 0, 5, 5, 0]
    runs = _find_low_runs(motion, threshold=1.0)
    assert runs == [(2, 5), (7, 8)]


def test_static_segment_detected_and_removed():
    fps = 30.0
    # 1초 움직임 -> 2초 정지 -> 1초 움직임
    motion = [10.0] * 30 + [0.0] * 60 + [10.0] * 30
    params = DetectParams(static_threshold=1.2, min_static_sec=1.0, pad_frames=0,
                          static_mode="cut")
    segs = detect_segments(motion, fps, params)

    removes = [s for s in segs if s.type == "remove"]
    assert len(removes) == 1
    assert removes[0].reason == "static"
    assert removes[0].start_frame == 30
    assert removes[0].end_frame == 90
    # 전체 타임라인이 빈틈없이 덮였는지
    assert segs[0].start_frame == 0
    assert segs[-1].end_frame == 120


def test_short_pause_is_kept():
    fps = 30.0
    # 0.1초(3프레임)짜리 멈칫은 무시되어야 한다 (min_freeze_sec=0.15 -> 4.5프레임)
    motion = [10.0] * 30 + [0.0] * 3 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, min_freeze_sec=0.15, pad_frames=0)
    segs = detect_segments(motion, fps, params)
    assert all(s.type == "keep" for s in segs)


def test_freeze_classified_as_stutter():
    fps = 30.0
    # 0.3초(9프레임) 얼어붙음 -> static(1s)에는 못 미치지만 freeze(0.15s)는 넘음
    motion = [10.0] * 30 + [0.0] * 9 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, min_freeze_sec=0.15, pad_frames=0)
    segs = detect_segments(motion, fps, params)
    removes = [s for s in segs if s.type == "remove"]
    assert len(removes) == 1
    assert removes[0].reason == "stutter"


def test_pad_frames_shrinks_remove_range():
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 60 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, pad_frames=5, static_mode="cut")
    segs = detect_segments(motion, fps, params)
    r = [s for s in segs if s.type == "remove"][0]
    assert r.start_frame == 35  # 30 + 5
    assert r.end_frame == 85    # 90 - 5


def test_pad_drops_tiny_range():
    fps = 30.0
    # freeze 6프레임인데 pad 5씩이면 6-10<0 -> 컷 버려짐
    motion = [10.0] * 10 + [0.0] * 6 + [10.0] * 10
    params = DetectParams(min_freeze_sec=0.15, pad_frames=5)
    segs = detect_segments(motion, fps, params)
    assert all(s.type == "keep" for s in segs)


def test_empty_motion():
    assert detect_segments([], 30.0, DetectParams()) == []


def test_auto_threshold_separates_small_motion():
    # 작은 피사체: 움직임 0.5, 정지 0.0. 고정 1.2면 전부 정지로 오인되지만
    # auto 모드는 분포에서 임계값을 낮춰 올바르게 분리해야 한다.
    fps = 30.0
    motion = [0.5] * 30 + [0.0] * 60 + [0.5] * 30
    params = DetectParams(auto_threshold=True, min_static_sec=1.0, pad_frames=0,
                          static_mode="cut")
    thr = compute_auto_threshold(motion, params)
    assert 0.0 < thr < 0.5
    segs = detect_segments(motion, fps, params)
    removes = [s for s in segs if s.type == "remove"]
    assert len(removes) == 1
    assert removes[0].start_frame == 30 and removes[0].end_frame == 90


def test_static_defaults_to_mark_not_cut():
    # DIY 기본값: 정지는 자르지 않고 '표시'만 해야 한다.
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 60 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, pad_frames=0)  # static_mode 기본 mark
    dets = detect_motion_segments(motion, fps, params)
    assert len(dets) == 1
    assert dets[0].type == "mark" and dets[0].reason == "static"


def test_stutter_defaults_to_cut():
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 9 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, min_freeze_sec=0.15, pad_frames=0)
    dets = detect_motion_segments(motion, fps, params)
    assert len(dets) == 1
    assert dets[0].type == "remove" and dets[0].reason == "stutter"


def test_mode_off_disables_detection():
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 60 + [10.0] * 30
    params = DetectParams(min_static_sec=1.0, static_mode="off")
    assert detect_motion_segments(motion, fps, params) == []


def _track(n, fps=30.0, motion=5.0, cx=0.5, cy=0.5, border=0.0):
    return MotionTrack(
        motion=[motion] * n, cx=[cx] * n, cy=[cy] * n, border_ratio=[border] * n,
        fps=fps, frame_count=n, width=1920, height=1080,
    )


def test_offcenter_detected_when_motion_drifts_to_edge():
    # 1초 내내 움직이는데 무게중심이 오른쪽 끝(0.9), 가장자리 에너지 집중(0.85)
    t = _track(30, motion=10.0, cx=0.9, cy=0.5, border=0.85)
    params = DetectParams(min_offcenter_sec=0.4, pad_frames=0)
    marks = detect_offcenter(t, params)
    assert len(marks) == 1
    assert marks[0].type == "mark" and marks[0].reason == "offcenter"


def test_centered_motion_not_flagged_offcenter():
    t = _track(30, motion=10.0, cx=0.5, cy=0.5, border=0.2)
    marks = detect_offcenter(t, DetectParams(min_offcenter_sec=0.4))
    assert marks == []


def test_static_at_edge_not_offcenter():
    # 가장자리에 있지만 '움직이지 않으면'(motion<threshold) 오프센터가 아니다.
    t = _track(30, motion=0.0, cx=0.95, cy=0.5, border=0.9)
    marks = detect_offcenter(t, DetectParams(static_threshold=1.2, min_offcenter_sec=0.4))
    assert marks == []


def test_offcenter_mode_off():
    t = _track(30, motion=10.0, cx=0.9, cy=0.5, border=0.85)
    marks = detect_offcenter(t, DetectParams(offcenter_mode="off"))
    assert marks == []


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)

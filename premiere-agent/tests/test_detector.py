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


def test_long_static_is_cut():
    fps = 30.0
    # 3초(90프레임) 정지 -> static_cut_sec(3.0) 이상이므로 컷
    motion = [10.0] * 30 + [0.0] * 90 + [10.0] * 30
    params = DetectParams(static_threshold=1.2, static_cut_sec=3.0, pad_frames=0)
    segs = detect_segments(motion, fps, params)
    removes = [s for s in segs if s.type == "remove"]
    assert len(removes) == 1
    assert removes[0].reason == "static"
    assert removes[0].start_frame == 30 and removes[0].end_frame == 120
    assert segs[0].start_frame == 0 and segs[-1].end_frame == 150


def test_medium_static_is_marked_not_cut():
    fps = 30.0
    # 2초(60프레임) 정지 -> mark(1.5s) 이상, cut(3.0s) 미만 -> 표시
    motion = [10.0] * 30 + [0.0] * 60 + [10.0] * 30
    params = DetectParams(static_mark_sec=1.5, static_cut_sec=3.0, pad_frames=0)
    dets = detect_motion_segments(motion, fps, params)
    assert len(dets) == 1
    assert dets[0].type == "mark" and dets[0].reason == "static"


def test_short_pause_is_kept():
    fps = 30.0
    # 0.1초(3프레임)짜리 멈칫은 무시 (min_freeze_sec=0.15 -> 4.5프레임)
    motion = [10.0] * 30 + [0.0] * 3 + [10.0] * 30
    params = DetectParams(min_freeze_sec=0.15, pad_frames=0)
    dets = detect_motion_segments(motion, fps, params)
    assert dets == []


def test_freeze_classified_as_stutter():
    fps = 30.0
    # 0.3초(9프레임) 얼어붙음 -> 정지 표시(1.5s)엔 못 미치지만 freeze(0.15s)는 넘음
    motion = [10.0] * 30 + [0.0] * 9 + [10.0] * 30
    params = DetectParams(min_freeze_sec=0.15, pad_frames=0)
    dets = detect_motion_segments(motion, fps, params)
    assert len(dets) == 1
    assert dets[0].type == "remove" and dets[0].reason == "stutter"


def test_pad_frames_shrinks_remove_range():
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 90 + [10.0] * 30
    params = DetectParams(static_cut_sec=3.0, pad_frames=5)
    segs = detect_segments(motion, fps, params)
    r = [s for s in segs if s.type == "remove"][0]
    assert r.start_frame == 35   # 30 + 5
    assert r.end_frame == 115    # 120 - 5


def test_pad_drops_tiny_range():
    fps = 30.0
    # freeze 6프레임인데 pad 5씩이면 6-10<0 -> 컷 버려짐
    motion = [10.0] * 10 + [0.0] * 6 + [10.0] * 10
    params = DetectParams(min_freeze_sec=0.15, pad_frames=5)
    segs = detect_segments(motion, fps, params)
    assert all(s.type == "keep" for s in segs)


def test_empty_motion():
    assert detect_segments([], 30.0, DetectParams()) == []


def test_disable_static_cut_with_high_threshold():
    # static_cut_sec 를 크게 두면 길어도 컷하지 않고 표시만.
    fps = 30.0
    motion = [10.0] * 30 + [0.0] * 90 + [10.0] * 30
    params = DetectParams(static_mark_sec=1.5, static_cut_sec=999, pad_frames=0)
    dets = detect_motion_segments(motion, fps, params)
    assert len(dets) == 1 and dets[0].type == "mark"


def test_auto_threshold_separates_small_motion():
    # 작은 피사체: 움직임 0.5, 정지 0.0. 고정 1.2면 전부 정지로 오인되지만
    # auto 모드는 분포에서 임계값을 낮춰 올바르게 분리해야 한다.
    fps = 30.0
    motion = [0.5] * 30 + [0.0] * 90 + [0.5] * 30
    params = DetectParams(auto_threshold=True, static_cut_sec=3.0, pad_frames=0)
    thr = compute_auto_threshold(motion, params)
    assert 0.0 < thr < 0.5
    segs = detect_segments(motion, fps, params)
    removes = [s for s in segs if s.type == "remove"]
    assert len(removes) == 1
    assert removes[0].start_frame == 30 and removes[0].end_frame == 120


def _track(n, fps=30.0, motion=5.0, cx=0.5, cy=0.5, center=0.6):
    return MotionTrack(
        motion=[motion] * n, cx=[cx] * n, cy=[cy] * n, center_ratio=[center] * n,
        fps=fps, frame_count=n, width=1920, height=1080,
    )


def test_offcenter_when_center_empty_while_working():
    # 작업 중(motion 높음)인데 중앙 엣지비율이 낮음 -> 중앙 피사체 빠짐
    t = _track(30, motion=10.0, center=0.1)
    params = DetectParams(center_content_thresh=0.30, min_offcenter_sec=0.4, pad_frames=0)
    marks = detect_offcenter(t, params)
    assert len(marks) == 1
    assert marks[0].type == "mark" and marks[0].reason == "offcenter"


def test_centered_content_not_flagged():
    # 중앙에 내용이 충분(center_ratio 높음) -> 정상
    t = _track(30, motion=10.0, center=0.6)
    marks = detect_offcenter(t, DetectParams(center_content_thresh=0.30, min_offcenter_sec=0.4))
    assert marks == []


def test_hands_on_side_with_central_object_not_flagged():
    # 손이 사이드에 있어도 중앙에 도구/작업물이 있으면(center_ratio 높음) 정상.
    t = _track(30, motion=15.0, cx=0.2, cy=0.5, center=0.55)
    marks = detect_offcenter(t, DetectParams(center_content_thresh=0.30, min_offcenter_sec=0.4))
    assert marks == []


def test_empty_center_but_static_not_flagged():
    # 중앙이 비었어도 '작업 중'이 아니면(정지) 오프센터로 보지 않는다.
    t = _track(30, motion=0.0, center=0.05)
    marks = detect_offcenter(t, DetectParams(static_threshold=1.2, min_offcenter_sec=0.4))
    assert marks == []


def test_offcenter_mode_off():
    t = _track(30, motion=10.0, center=0.1)
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

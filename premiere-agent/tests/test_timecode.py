"""타임코드 변환 테스트."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pp_autocut.timecode import (  # noqa: E402
    frames_to_seconds,
    seconds_to_frames,
    frames_to_timecode,
)


def test_frames_to_seconds():
    assert frames_to_seconds(30, 30.0) == 1.0
    assert frames_to_seconds(0, 30.0) == 0.0


def test_seconds_to_frames_roundtrip():
    assert seconds_to_frames(2.0, 25.0) == 50


def test_timecode_zero():
    assert frames_to_timecode(0, 30.0) == "00:00:00:00"


def test_timecode_one_second():
    assert frames_to_timecode(30, 30.0) == "00:00:01:00"


def test_timecode_minutes_and_frames():
    # 1분 5초 + 12프레임 @ 30fps = 30*65 + 12 = 1962
    assert frames_to_timecode(1962, 30.0) == "00:01:05:12"


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

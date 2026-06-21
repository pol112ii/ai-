"""프레임 <-> 시간/타임코드 변환 유틸.

MVP에서는 논드롭 프레임(Non-Drop Frame) 타임코드를 사용한다.
29.97fps 같은 드롭프레임 소스에서는 실제 타임코드와 미세한 오차가 있을 수 있으나,
프리미어로 넘기는 컷 지점은 '프레임 번호'를 기준으로 삼으므로 정확하다.
타임코드 문자열은 사람이 보기 위한 보조 정보다.
"""

from __future__ import annotations


def frames_to_seconds(frame: int, fps: float) -> float:
    return frame / fps if fps else 0.0


def seconds_to_frames(seconds: float, fps: float) -> int:
    return int(round(seconds * fps))


def frames_to_timecode(frame: int, fps: float) -> str:
    """프레임 번호를 HH:MM:SS:FF 논드롭 타임코드 문자열로 변환."""
    fps_int = max(1, int(round(fps)))
    frame = max(0, int(frame))
    ff = frame % fps_int
    total_seconds = frame // fps_int
    ss = total_seconds % 60
    mm = (total_seconds // 60) % 60
    hh = total_seconds // 3600
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"

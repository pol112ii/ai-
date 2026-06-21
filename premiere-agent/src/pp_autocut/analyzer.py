"""영상에서 프레임별 모션 특징을 계산한다.

각 프레임마다 직전 프레임과의 절대 차분(diff)을 구해 다음을 뽑는다.
- motion       : diff 평균(0~100). 작을수록 '움직임 없음'.
- cx, cy        : 모션 무게중심 위치(0~1, 0.5=중앙). 손이 어디서 움직이는지.
- border_ratio  : 중앙 안전영역 '밖'에 모인 모션 비율(0~1). 가장자리 잘림 신호.

cx/cy/border_ratio 는 '손이 중앙에서 벗어나 가장자리에서 잘리는' 오프센터 구간을
표시하기 위한 공간 정보다.

OpenCV(cv2)가 필요하다. 없으면 명확한 안내와 함께 예외를 던진다.
"""

from __future__ import annotations

import numpy as np

from .models import MotionTrack

try:
    import cv2
except ImportError as exc:  # pragma: no cover - 환경 의존
    raise ImportError(
        "opencv가 필요합니다. `pip install -r requirements.txt` 로 설치하세요."
    ) from exc


def _resize_gray(frame: np.ndarray, target_width: int) -> np.ndarray:
    h, w = frame.shape[:2]
    if target_width and w > target_width:
        scale = target_width / w
        frame = cv2.resize(frame, (target_width, max(1, int(h * scale))))
    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


def _spatial_features(diff: np.ndarray, safe_zone: float):
    """diff 맵에서 (cx, cy, border_ratio) 계산. 무게중심과 가장자리 집중도."""
    h, w = diff.shape[:2]
    total = float(diff.sum())
    if total <= 0:
        return 0.5, 0.5, 0.0

    m = cv2.moments(diff, binaryImage=False)
    cx = (m["m10"] / m["m00"]) / w if m["m00"] else 0.5
    cy = (m["m01"] / m["m00"]) / h if m["m00"] else 0.5

    # 중앙 안전영역(가운데 safe_zone 비율) 안쪽 에너지 비율
    margin = (1.0 - safe_zone) / 2.0
    x0, x1 = int(w * margin), int(w * (1.0 - margin))
    y0, y1 = int(h * margin), int(h * (1.0 - margin))
    inside = float(diff[y0:y1, x0:x1].sum())
    border_ratio = 1.0 - (inside / total)
    return cx, cy, border_ratio


def analyze(path: str, downscale_width: int = 320, safe_zone: float = 0.6) -> MotionTrack:
    """영상을 스트리밍하며 프레임별 모션 특징(MotionTrack)을 만든다."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    track = MotionTrack(width=width, height=height)
    prev = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = _resize_gray(frame, downscale_width)
            if prev is None:
                track.motion.append(0.0)
                track.cx.append(0.5)
                track.cy.append(0.5)
                track.border_ratio.append(0.0)
            else:
                diff = cv2.absdiff(gray, prev)
                track.motion.append(float(diff.mean()) * 100.0 / 255.0)
                cx, cy, br = _spatial_features(diff, safe_zone)
                track.cx.append(cx)
                track.cy.append(cy)
                track.border_ratio.append(br)
            prev = gray
    finally:
        cap.release()

    track.frame_count = len(track.motion)
    track.fps = fps if fps > 0 else 30.0  # 메타데이터 없으면 안전한 기본값
    return track


# 하위 호환: 기존 스칼라 모션만 필요할 때.
def analyze_motion(path: str, downscale_width: int = 320):
    t = analyze(path, downscale_width=downscale_width)
    return t.motion, t.fps, t.frame_count, t.width, t.height

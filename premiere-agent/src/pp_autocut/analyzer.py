"""영상에서 프레임별 모션 + '내용(구도)' 특징을 계산한다.

프레임마다 두 갈래를 뽑는다.
- 모션(정지/버벅용): 직전 프레임과의 절대 차분 평균(0~100). 작을수록 멈춤.
- 내용/구도(오프센터용): 현재 프레임의 엣지(Sobel) 에너지로
    cx, cy        : 엣지 무게중심(0~1, 0.5=중앙) = '작업물·도구가 어디 있나'
    center_ratio  : 중앙 안전영역 안의 엣지 비율(0~1) = '중앙에 내용이 얼마나 있나'

핵심: 손은 사이드에 있는 게 정상이므로 '모션 위치'가 아니라 '화면 내용이 중앙에
모여 있는가'로 구도를 판단한다.

OpenCV(cv2)가 필요하다.
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


def _content_features(gray: np.ndarray, safe_zone: float):
    """엣지 맵에서 (cx, cy, center_ratio) 계산.

    cx, cy        : 엣지 무게중심(0~1).
    center_ratio  : 중앙 안전영역 안의 엣지 에너지 / 전체 엣지 에너지.
    """
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)

    h, w = mag.shape[:2]
    total = float(mag.sum())
    if total <= 0:
        return 0.5, 0.5, 0.0

    m = cv2.moments(mag, binaryImage=False)
    cx = (m["m10"] / m["m00"]) / w if m["m00"] else 0.5
    cy = (m["m01"] / m["m00"]) / h if m["m00"] else 0.5

    margin = (1.0 - safe_zone) / 2.0
    x0, x1 = int(w * margin), int(w * (1.0 - margin))
    y0, y1 = int(h * margin), int(h * (1.0 - margin))
    inside = float(mag[y0:y1, x0:x1].sum())
    center_ratio = inside / total
    return cx, cy, center_ratio


def analyze(path: str, downscale_width: int = 320, safe_zone: float = 0.6) -> MotionTrack:
    """영상을 스트리밍하며 프레임별 특징(MotionTrack)을 만든다."""
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

            # 모션(정지/버벅)
            if prev is None:
                track.motion.append(0.0)
            else:
                diff = cv2.absdiff(gray, prev)
                track.motion.append(float(diff.mean()) * 100.0 / 255.0)
            prev = gray

            # 내용/구도(오프센터)
            cx, cy, cr = _content_features(gray, safe_zone)
            track.cx.append(cx)
            track.cy.append(cy)
            track.center_ratio.append(cr)
    finally:
        cap.release()

    track.frame_count = len(track.motion)
    track.fps = fps if fps > 0 else 30.0  # 메타데이터 없으면 안전한 기본값
    return track


# 하위 호환: 기존 스칼라 모션만 필요할 때.
def analyze_motion(path: str, downscale_width: int = 320):
    t = analyze(path, downscale_width=downscale_width)
    return t.motion, t.fps, t.frame_count, t.width, t.height

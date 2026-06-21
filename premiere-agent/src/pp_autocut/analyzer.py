"""영상에서 프레임별 모션 점수를 계산한다.

핵심 아이디어: 연속한 두 프레임의 차이가 작을수록 '움직임이 없다'고 본다.
- 그레이스케일로 변환하고 가로 폭을 줄여 계산 비용을 낮춘다.
- 직전 프레임과의 절대 차분 평균을 0~100으로 정규화해 모션 점수로 쓴다.

OpenCV(cv2)가 필요하다. 설치되어 있지 않으면 명확한 안내와 함께 예외를 던진다.
"""

from __future__ import annotations

from typing import List, Tuple

import numpy as np

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


def analyze_motion(
    path: str, downscale_width: int = 320
) -> Tuple[List[float], float, int, int, int]:
    """영상을 스트리밍하며 프레임별 모션 점수 배열을 만든다.

    반환: (motion_scores, fps, frame_count, width, height)
    motion_scores[i] = 프레임 i 와 i-1 사이의 모션(0~100). 0번 프레임은 0.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상을 열 수 없습니다: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    motion: List[float] = []
    prev = None
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            gray = _resize_gray(frame, downscale_width)
            if prev is None:
                motion.append(0.0)
            else:
                diff = cv2.absdiff(gray, prev)
                # 평균 절대차분(0~255)을 0~100 점수로 정규화.
                motion.append(float(diff.mean()) * 100.0 / 255.0)
            prev = gray
    finally:
        cap.release()

    frame_count = len(motion)
    if fps <= 0:
        fps = 30.0  # 메타데이터가 없으면 안전한 기본값
    return motion, fps, frame_count, width, height

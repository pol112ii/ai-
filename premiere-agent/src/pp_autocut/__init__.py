"""pp_autocut: 프리미어프로 자동 컷편집 에이전트 - 영상 분석부.

정지(움직임 없는) 구간과 버벅(짧게 얼어붙는) 구간을 검출해
프리미어 패널이 적용할 컷 계획(JSON)을 만든다.
"""

from .models import AnalysisResult, DetectParams, Segment
from .detector import build_result, detect_segments
from .exporter import to_dict, write_json

__all__ = [
    "AnalysisResult",
    "DetectParams",
    "Segment",
    "build_result",
    "detect_segments",
    "to_dict",
    "write_json",
]

__version__ = "0.1.0"

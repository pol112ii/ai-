"""분석부 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Literal

SegmentType = Literal["keep", "remove"]
RemoveReason = Literal["static", "stutter", ""]


@dataclass
class DetectParams:
    """정지/버벅 검출 파라미터.

    수치는 모두 0~100 정규화된 모션 점수(평균 프레임 차분 기준)를 기준으로 한다.
    """

    # 이 값보다 모션이 작으면 '거의 정지' 프레임으로 본다.
    static_threshold: float = 1.2
    # 이 길이(초) 이상 정지가 이어지면 '정지 장면(static)'으로 보고 컷 대상.
    min_static_sec: float = 1.0
    # 움직이던 중에 짧게 얼어붙는(중복 프레임) 버벅임 최소 길이(초).
    min_freeze_sec: float = 0.15
    # 컷할 구간 앞뒤로 남겨둘 핸들(프레임). 너무 빡빡하게 자르지 않도록 여유를 둔다.
    pad_frames: int = 2
    # 분석 속도를 위해 프레임을 이 가로 폭으로 축소한 뒤 모션을 계산한다.
    downscale_width: int = 320

    # 임계값 자동 산출: 영상 자체의 모션 분포에서 static_threshold 를 정한다.
    # 피사체가 화면에서 차지하는 비율이 영상마다 달라도 잘 동작하게 해준다.
    # effective = max(auto_floor, percentile(motion, auto_percentile) * auto_ratio)
    auto_threshold: bool = False
    auto_percentile: float = 75.0
    auto_ratio: float = 0.3
    auto_floor: float = 0.2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Segment:
    """타임라인의 한 구간 (keep 또는 remove)."""

    type: SegmentType
    start_frame: int
    end_frame: int  # exclusive
    reason: RemoveReason = ""

    @property
    def length_frames(self) -> int:
        return self.end_frame - self.start_frame

    def length_sec(self, fps: float) -> float:
        return self.length_frames / fps if fps else 0.0


@dataclass
class AnalysisResult:
    source: str
    fps: float
    frame_count: int
    width: int
    height: int
    params: DetectParams
    segments: List[Segment] = field(default_factory=list)

    @property
    def remove_segments(self) -> List[Segment]:
        return [s for s in self.segments if s.type == "remove"]

    @property
    def removed_frames(self) -> int:
        return sum(s.length_frames for s in self.remove_segments)

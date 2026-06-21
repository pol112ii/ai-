"""분석부 데이터 모델."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Literal

# keep  : 그대로 둠
# remove: 실제로 잘라냄(리플 삭제)
# mark  : 자르지 않고 프리미어 마커로 '표시'만 함
SegmentType = Literal["keep", "remove", "mark"]
# 검출 사유
Reason = Literal["static", "stutter", "offcenter", ""]
# 유형별 처리 방식
Mode = Literal["cut", "mark", "off"]


@dataclass
class DetectParams:
    """정지/버벅/오프센터 검출 파라미터.

    모션 점수는 0~100 으로 정규화된 평균 프레임 차분 기준이다.
    """

    # --- 모션(정지/버벅) ---
    # 이 값보다 모션이 작으면 '거의 정지' 프레임으로 본다.
    static_threshold: float = 1.2
    # 정지 길이(초)에 따른 처리 (긴 정지일수록 강하게).
    #   static_cut_sec 이상  -> 자동 컷 (확실한 데드 구간)
    #   static_mark_sec 이상 -> 표시만 (사람이 검수)
    #   그보다 짧으면          -> 그대로 둠 (자연스러운 멈칫)
    # mark 단계를 끄려면 static_mark_sec 를 static_cut_sec 이상으로 둔다.
    static_mark_sec: float = 1.5
    static_cut_sec: float = 3.0
    # 움직이던 중에 짧게 얼어붙는(중복 프레임) 버벅임 최소 길이(초).
    min_freeze_sec: float = 0.15
    # 컷/표시 구간 앞뒤로 남겨둘 핸들(프레임).
    pad_frames: int = 2
    # 분석 속도를 위해 프레임을 이 가로 폭으로 축소한 뒤 계산한다.
    downscale_width: int = 320

    # --- 유형별 처리 방식 (cut=잘라냄, mark=표시만, off=무시) ---
    # 버벅임만 자동 컷, 오프센터(구도)는 표시만. 정지는 위 길이 규칙을 따른다.
    stutter_mode: Mode = "cut"
    offcenter_mode: Mode = "mark"

    # --- 오프센터(중앙 피사체 빠짐 / 구도 이탈) ---
    # 핵심: '손이 어디 있나'가 아니라 '중앙에 작업물·도구가 잘 보이나'.
    # DIY 구조상 손은 사이드에 있는 게 정상이므로 손 위치로 판단하지 않는다.
    # 대신 화면 '내용(엣지 밀도)'이 중앙 안전영역에 얼마나 모여 있는지로 본다.
    #
    # 화면 중앙의 '안전 영역' 비율. 0.6 이면 가로/세로 가운데 60%가 안전 영역.
    safe_zone: float = 0.6
    # 중앙 안전영역 안의 엣지 에너지 비율이 이 값 미만이면 '중앙이 비었다'고 본다.
    # (작업물/도구가 중앙에서 잘 안 보이는 상태)
    center_content_thresh: float = 0.30
    # 정지가 아니라 '작업 중'일 때만 본다(움직임이 있어야 검출).
    offcenter_requires_motion: bool = True
    # 이 길이(초) 이상 이어져야 표시한다.
    min_offcenter_sec: float = 0.6

    # --- 임계값 자동 산출 ---
    # 영상 자체의 모션 분포에서 static_threshold 를 정한다.
    # effective = max(auto_floor, percentile(motion, auto_percentile) * auto_ratio)
    auto_threshold: bool = False
    auto_percentile: float = 75.0
    auto_ratio: float = 0.3
    auto_floor: float = 0.2

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Segment:
    """타임라인의 한 구간 (keep / remove / mark)."""

    type: SegmentType
    start_frame: int
    end_frame: int  # exclusive
    reason: Reason = ""

    @property
    def length_frames(self) -> int:
        return self.end_frame - self.start_frame

    def length_sec(self, fps: float) -> float:
        return self.length_frames / fps if fps else 0.0


@dataclass
class MotionTrack:
    """프레임별 모션 특징 시계열. analyzer 가 만들고 detector 가 소비한다."""

    motion: List[float] = field(default_factory=list)        # 0~100 모션 점수(프레임 차분)
    cx: List[float] = field(default_factory=list)            # 내용(엣지) 무게중심 x (0~1, 0.5=중앙)
    cy: List[float] = field(default_factory=list)            # 내용(엣지) 무게중심 y (0~1, 0.5=중앙)
    center_ratio: List[float] = field(default_factory=list)  # 안전영역 '안'의 엣지 에너지 비율 (0~1)
    fps: float = 30.0
    frame_count: int = 0
    width: int = 0
    height: int = 0


@dataclass
class AnalysisResult:
    source: str
    fps: float
    frame_count: int
    width: int
    height: int
    params: DetectParams
    # 컷 타임라인(keep/remove 로 전체를 빈틈없이 덮음)
    segments: List[Segment] = field(default_factory=list)
    # 자르지 않고 표시만 하는 마커들(컷 타임라인과 별개로 겹쳐 올림)
    marks: List[Segment] = field(default_factory=list)

    @property
    def remove_segments(self) -> List[Segment]:
        return [s for s in self.segments if s.type == "remove"]

    @property
    def removed_frames(self) -> int:
        return sum(s.length_frames for s in self.remove_segments)

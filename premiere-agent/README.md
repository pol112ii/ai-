# 프리미어프로 자동 컷편집 에이전트

DIY 키트 과정 촬영 영상에서

- **움직임이 멈춘 정지 구간** → 자르지 않고 **표시(마커)만**
- **손이 중앙에서 벗어나 화면 가장자리에서 잘리며 동작이 이어지는 구간** → **표시(마커)만**
- **짧게 얼어붙는 버벅임(중복/프리즈 프레임)** → **자동 컷**

을 찾아주는 도구입니다. "자를 것"과 "사람이 검수하게 표시만 할 것"을 분리합니다.

```
[영상] → (1) 분석부 (Python) → cuts.json → (2) 프리미어 패널 (CEP/ExtendScript) → 컷 + 마커
```

- **(1) 분석부 — 지금 구현된 부분.** 영상을 프레임 단위로 분석해 컷·마커 계획을
  `cuts.json`(스키마 `pp-autocut/v2`)으로 만든다.
- **(2) 프리미어 패널 — 다음 단계.** `cuts.json`을 읽어 시퀀스에 컷을 적용하고
  마커를 찍는다. 설계 메모는 [`panel/README.md`](panel/README.md) 참고.

> 오디오 무음컷은 **하지 않습니다.** DIY 과정 촬영은 거의 무음이라 무음 기준 컷은
> 의미가 없어서 제외했습니다.

---

## 무엇을, 어떻게 처리하나

| 유형 | 무엇을 잡나 | 기본 처리 | 마커 색 |
|------|-------------|-----------|---------|
| `static` | 움직임이 없는 정지 구간 | **표시(mark)** | 노랑 |
| `offcenter` | 손이 중앙을 벗어나 가장자리에서 잘리며 동작이 이어지는 구간 | **표시(mark)** | 빨강 |
| `stutter` | 움직이다 잠깐 얼어붙는 버벅임(프리즈/중복 프레임) | **컷(cut)** | 하늘 |

유형별 처리 방식은 `cut`(잘라냄) / `mark`(표시만) / `off`(무시)로 바꿀 수 있다.
예: 정지도 자동으로 자르고 싶으면 `--static-mode cut`.

## 동작 원리

**정지·버벅 (모션 크기)**
연속한 두 프레임의 절대 차분 평균을 0~100 모션 점수로 계산한다. `static_threshold`
미만이 일정 시간 이어지면 정지(`min_static_sec` 이상) 또는 버벅임(`min_freeze_sec`
이상)으로 본다. 그보다 짧은 멈칫은 자연스러운 동작으로 보고 남긴다.

**오프센터 (모션 위치)**
프레임마다 **모션 무게중심(cx, cy)**과 **안전영역 밖 모션 비율(border_ratio)**을
구한다. "움직이는 중인데(active)" 무게중심이 중앙에서 멀고(`center_dist_thresh`)
가장자리에 모션이 집중되면(`border_ratio_thresh`), 손이 화면 밖으로 벗어나 잘리는
구간으로 보고 표시한다. 움직임이 없으면(정지) 오프센터로 보지 않는다 —
"동작으로 이어지는" 경우만 잡는다.

> **임계값 자동 산출(`--auto-threshold`)**
> 전체 평균 차분은 피사체가 화면에서 차지하는 비율에 따라 절대값이 달라진다.
> (손이 화면을 꽉 채우면 크고, 작으면 작다.) 이 옵션을 켜면 영상 자체의 모션
> 분포에서 임계값을 정하므로 영상마다 수동 조정 없이 동작한다. 처음 써본다면 권장.

---

## 설치

```bash
cd premiere-agent
pip install -r requirements.txt
```

Python 3.9+ 권장. Windows / macOS 모두 동작.

## 사용법

```bash
# 권장: 임계값 자동 + DIY 기본값(정지·오프센터 표시, 버벅임 컷)
python -m pp_autocut input.mp4 --auto-threshold

# 정지도 함께 자동 컷하고 싶을 때
python -m pp_autocut input.mp4 --static-mode cut

# 버벅임은 자르지 말고 표시만 하고 싶을 때
python -m pp_autocut input.mp4 --stutter-mode mark

# 오프센터 검출 끄기
python -m pp_autocut input.mp4 --offcenter-mode off
```

설치 없이 바로 실행할 땐 `PYTHONPATH=src`를 붙인다.

```bash
PYTHONPATH=src python -m pp_autocut input.mp4 --auto-threshold
```

### 출력 요약 예시

```
[pp_autocut] input.mp4
  해상도 1920x1080 | 29.97fps | 5400프레임 (180.2s)
  ✂️  컷 4개 | 92프레임 (3.1s)
  🔖 표시 11개 (static 7, offcenter 4)
  -> input.cuts.json
```

---

## 정확도 튜닝 (진단 도구)

검출이 맞는지 '눈으로' 보면서 임계값을 맞추기 위한 도구를 제공한다.

```bash
# 미리보기 영상 + 지표 CSV + 임계값 추천을 한 번에
python -m pp_autocut clip.mp4 --auto-threshold \
    --preview clip_preview.mp4 --metrics-csv clip.csv --calibrate
```

- `--preview OUT.mp4` : 원본 위에 **안전영역 박스(초록) · 모션 무게중심 점(흰) ·
  모션 점수 · 검출 라벨([MARK]/[CUT] STATIC/OFF-CENTER/STUTTER, 색 테두리)** 을
  입힌 미리보기 영상. 어디를 어떻게 잡았는지 한눈에 보인다.
- `--metrics-csv OUT.csv` : 프레임별 `motion, cx, cy, border_ratio, kind, reason`.
  엑셀로 그래프 그려 임계값을 정밀 조정할 때 쓴다.
- `--calibrate` : 클립의 모션 분포(분위수)와 **추천 `static_threshold`**,
  움직이는 프레임의 무게중심거리/가장자리비율 분포를 출력. 오프센터 임계값
  (`center_dist_thresh`, `border_ratio_thresh`)을 정할 때 참고한다.

### 튜닝 순서(권장)

1. `--auto-threshold --preview --calibrate` 로 한 번 돌려 미리보기를 본다.
2. 정지가 덜/과하게 잡히면 → `--static-threshold` 또는 `--min-static-sec` 조정.
3. 오프센터가 덜/과하게 잡히면 → `--center-dist-thresh`(작을수록 민감),
   `border_ratio_thresh`, `--min-offcenter-sec` 조정. `--calibrate`의 분위수를 기준으로.
4. 만족하면 그 값을 `config.json`에 저장해 재사용한다.

---

## 파라미터

| 이름 | 기본값 | 설명 |
|------|--------|------|
| `static_threshold` | 1.2 | 이 값 미만 모션이면 '거의 정지' 프레임(0~100) |
| `min_static_sec` | 1.0 | 이 길이 이상 정지면 정지 구간 |
| `min_freeze_sec` | 0.15 | 버벅임으로 볼 최소 길이 |
| `pad_frames` | 2 | 컷/표시 구간 앞뒤 핸들(프레임) |
| `downscale_width` | 320 | 분석 시 축소 가로 폭(클수록 정확·느림) |
| `static_mode` | `mark` | 정지 처리: cut/mark/off |
| `stutter_mode` | `cut` | 버벅임 처리: cut/mark/off |
| `offcenter_mode` | `mark` | 오프센터 처리: cut/mark/off |
| `safe_zone` | 0.6 | 화면 중앙 안전영역 비율 |
| `center_dist_thresh` | 0.28 | 무게중심이 중앙에서 이만큼 벗어나면 오프센터(0=중앙,0.5=끝) |
| `border_ratio_thresh` | 0.72 | 안전영역 밖 모션 비율이 이 값 이상이면 '잘림' |
| `require_border_clip` | true | 가장자리 잘림 조건도 함께 요구 |
| `min_offcenter_sec` | 0.4 | 오프센터로 표시할 최소 길이 |
| `auto_threshold` | false | 모션 분포로 `static_threshold` 자동 산출 |

> 오프센터 임계값(`center_dist_thresh`, `border_ratio_thresh`)은 실제 촬영 구도에
> 따라 조정이 필요할 수 있다. 손이 차지하는 위치/크기가 영상마다 다르기 때문.

---

## 출력 형식 (`cuts.json`, 스키마 `pp-autocut/v2`)

프리미어 패널이 소비할 계약(contract)이다.

- `fps`, `frame_count`, `duration_sec`, `resolution`, `params`
- `summary`: 컷 개수/프레임/초, 표시 개수, 사유별 표시 개수
- `cut_points`: 면도날(razor)로 자를 **프레임 위치** 목록 (cut 모드 항목만)
- `remove_ranges`: 리플 삭제할 구간 `{reason, start_frame, end_frame, ...}`
- `markers`: 자르지 않고 마커로 표시할 항목
  `{reason, start_frame, end_frame, color, name, comment, ...}`
- `segments`: 컷 타임라인 전체(keep/remove 로 빈틈없이 덮음)

> 프레임 번호가 1차 기준, 초(`*_sec`)·타임코드(`*_tc`)는 참고용.
> 타임코드는 논드롭 기준이라 29.97fps 등에선 실제 TC와 미세한 차이가 있을 수 있다.

---

## 테스트

```bash
python tests/test_detector.py
python tests/test_timecode.py
```

검출/타임코드 로직 테스트는 OpenCV 없이 합성 데이터로 돌아간다.

---

## 프로젝트 구조

```
premiere-agent/
├─ src/pp_autocut/
│  ├─ analyzer.py    # 영상 → 프레임별 모션 점수 + 무게중심/가장자리 (OpenCV)
│  ├─ detector.py    # 정지/버벅/오프센터 검출, cut·mark 분기 (순수 로직)
│  ├─ exporter.py    # 결과 → cuts.json (pp-autocut/v2)
│  ├─ timecode.py    # 프레임 <-> 초/타임코드
│  ├─ models.py      # 데이터 모델/파라미터
│  └─ cli.py         # 커맨드라인
├─ tests/            # 단위 테스트 (OpenCV 불필요)
├─ panel/            # 프리미어 CEP/ExtendScript 패널 (다음 단계)
├─ requirements.txt
└─ config.example.json
```

## 로드맵

- [x] 분석부: 정지·오프센터 표시 + 버벅임 컷 → `cuts.json`
- [ ] 프리미어 CEP/ExtendScript 패널: 컷 적용 + 마커 찍기
- [ ] 오프센터 정밀도 개선(스킨/손 검출 기반)
- [ ] 미리보기 UI / 컷 전 사람 검수 모드
```

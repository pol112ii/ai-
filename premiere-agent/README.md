# 프리미어프로 자동 컷편집 에이전트

영상에서 **움직임이 멈춘 정지 장면**과 **짧게 얼어붙는 버벅임(중복/프리즈 프레임)**을
자동으로 찾아 컷 편집을 도와주는 도구입니다.

전체 그림은 두 부분으로 나뉩니다.

```
[영상 파일] → (1) 분석부 (Python) → cuts.json → (2) 프리미어 패널 (CEP/ExtendScript) → 타임라인 컷
```

- **(1) 분석부 — 이 저장소에서 지금 구현된 부분.** 영상을 프레임 단위로 분석해
  잘라낼 구간을 `cuts.json`(스키마 `pp-autocut/v1`)으로 만든다.
- **(2) 프리미어 패널 — 다음 단계.** `cuts.json`을 읽어 현재 시퀀스를 자동으로 컷한다.
  설계 메모는 [`panel/README.md`](panel/README.md) 참고.

---

## 동작 원리 (분석부)

1. 영상을 스트리밍하며 **연속한 두 프레임의 차이(절대 차분 평균)**를 0~100 점수로 계산한다.
   점수가 낮을수록 "움직임이 없다"는 뜻이다.
2. 점수가 `static_threshold` 미만인 프레임을 모아 **저모션 구간**을 만든다.
3. 구간 길이로 분류한다.
   - `min_static_sec` 이상 → **정지 장면(static)** → 컷 대상
   - `min_freeze_sec` 이상 → **버벅임(stutter)** → 컷 대상
   - 그보다 짧으면 → 자연스러운 멈칫으로 보고 **남김**
4. 컷 구간 앞뒤로 `pad_frames`만큼 핸들을 남겨 너무 빡빡하게 자르지 않는다.

> **임계값 자동 산출(`--auto-threshold`)**
> 전체 평균 차분은 피사체가 화면에서 차지하는 비율에 따라 절대값이 달라진다.
> (손이 화면을 꽉 채우면 크고, 작은 물체면 작다.) `--auto-threshold`를 켜면 영상
> 자체의 모션 분포에서 임계값을 정하므로 영상마다 수동 조정 없이 잘 동작한다.
> 어떤 임계값을 쓸지 모르겠다면 이 옵션을 먼저 써보길 권한다.

---

## 설치

```bash
cd premiere-agent
pip install -r requirements.txt
```

Python 3.9+ 권장. Windows / macOS 모두 동작한다.

## 사용법

```bash
# 기본 (고정 임계값)
python -m pp_autocut input.mp4 -o cuts.json

# 임계값 자동 (추천: 처음 써본다면)
python -m pp_autocut input.mp4 --auto-threshold

# 파라미터 직접 조정
python -m pp_autocut input.mp4 --static-threshold 1.5 --min-static-sec 0.8 --pad-frames 3

# 설정 파일 사용
python -m pp_autocut input.mp4 -c config.example.json
```

`src` 디렉터리가 패키지 경로이므로, 설치 없이 바로 실행할 땐 `PYTHONPATH=src`를 붙인다.

```bash
PYTHONPATH=src python -m pp_autocut input.mp4 --auto-threshold
```

### 출력 요약 예시

```
[pp_autocut] input.mp4
  해상도 1920x1080 | 29.97fps | 5400프레임 (180.2s)
  제거 구간 12개 | 640프레임 (21.4s) 컷
  -> input.cuts.json
```

---

## 파라미터

| 이름 | 기본값 | 설명 |
|------|--------|------|
| `static_threshold` | 1.2 | 이 값 미만 모션이면 '거의 정지' 프레임 (0~100 점수) |
| `min_static_sec` | 1.0 | 이 길이 이상 정지가 이어지면 정지 장면으로 컷 |
| `min_freeze_sec` | 0.15 | 움직이다 잠깐 얼어붙는 버벅임 최소 길이 |
| `pad_frames` | 2 | 컷 구간 앞뒤로 남길 핸들(프레임) |
| `downscale_width` | 320 | 분석 시 축소할 가로 폭 (클수록 정확·느림) |
| `auto_threshold` | false | 모션 분포로 `static_threshold` 자동 산출 |
| `auto_percentile` | 75 | 자동 산출 시 참조할 분위수 |
| `auto_ratio` | 0.3 | 분위수 값에 곱할 비율 |
| `auto_floor` | 0.2 | 자동 임계값의 최소 바닥값 |

---

## 출력 형식 (`cuts.json`, 스키마 `pp-autocut/v1`)

프리미어 패널이 소비할 계약(contract)이다. 핵심 필드:

- `fps`, `frame_count`, `duration_sec`, `resolution`
- `params`: 실제 사용된 파라미터 (auto면 산출된 `static_threshold` 포함)
- `summary`: 제거 구간 수 / 제거 프레임 / 제거 초
- `cut_points`: 면도날(razor)로 자를 **프레임 위치** 목록
- `remove_ranges`: 리플 삭제할 구간 `{start_frame, end_frame, reason, ...}`
- `segments`: 타임라인 전체를 빈틈없이 덮는 keep/remove 목록

> 프레임 번호가 1차 기준이고, 초(`*_sec`)·타임코드(`*_tc`)는 참고용이다.
> 타임코드는 논드롭 기준이라 29.97fps 같은 소스에선 실제 TC와 미세한 차이가 있을 수 있다.

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
│  ├─ analyzer.py    # 영상 → 프레임별 모션 점수 (OpenCV)
│  ├─ detector.py    # 모션 점수 → 정지/버벅 구간 검출 (순수 로직)
│  ├─ exporter.py    # 결과 → cuts.json (pp-autocut/v1)
│  ├─ timecode.py    # 프레임 <-> 초/타임코드
│  ├─ models.py      # 데이터 모델/파라미터
│  └─ cli.py         # 커맨드라인
├─ tests/            # 단위 테스트 (OpenCV 불필요)
├─ panel/            # 프리미어 CEP/ExtendScript 패널 (다음 단계)
├─ requirements.txt
└─ config.example.json
```

## 로드맵

- [x] 분석부 MVP: 정지/버벅 검출 → `cuts.json`
- [ ] 프리미어 CEP/ExtendScript 패널: `cuts.json` 읽어 자동 컷 적용
- [ ] 오디오 기반 무음 구간 컷(말 사이 공백) 병행
- [ ] 옵티컬 플로우 기반 정밀 모션(전역 평균의 한계 보완)
- [ ] 미리보기 UI / 컷 전 사람 검수 모드
```

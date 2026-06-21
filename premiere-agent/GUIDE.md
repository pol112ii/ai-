# 적용 가이드 (Windows)

이 도구를 설치하고, 내 DIY 영상에 돌리고, 결과를 프리미어에 적용하는 전체 흐름입니다.
컴퓨터에 익숙하지 않아도 따라 할 수 있게 한 단계씩 적었습니다.

> **지금 단계 요약**
> - ✅ **분석부**(영상 분석 → 컷·표시 계획)와 **진단 도구**(미리보기/검수)는 완성됐습니다.
> - ⏳ 프리미어에 **자동으로** 컷을 넣어주는 **패널**은 다음 단계입니다(아직 미구현).
> - 그래서 지금은 ① 분석 → ② 미리보기로 검수 → ③ 프리미어에 **반자동/수동 적용**
>   흐름으로 씁니다. 패널이 나오면 ③이 버튼 한 번으로 바뀝니다.

---

## 1단계. 파이썬 설치 (최초 1회)

1. https://www.python.org/downloads/ 에서 **Python 3.11**(또는 3.9+) 설치.
2. 설치 첫 화면에서 **"Add python.exe to PATH"** 체크박스를 꼭 켜고 설치.
3. 설치 확인: 시작 메뉴에서 **PowerShell** 열고 아래 입력 → 버전이 보이면 성공.
   ```powershell
   python --version
   ```

## 2단계. 도구 내려받기 & 의존성 설치 (최초 1회)

1. 이 저장소를 내려받는다(ZIP 다운로드 또는 git clone).
2. PowerShell에서 `premiere-agent` 폴더로 이동.
   ```powershell
   cd 경로\premiere-agent
   ```
3. 필요한 라이브러리 설치.
   ```powershell
   pip install -r requirements.txt
   ```

## 3단계. 내 영상에 돌리기

분석할 영상 파일(예: `D:\촬영\diy_01.mp4`)을 준비하고 아래 실행:

```powershell
python -m pp_autocut "D:\촬영\diy_01.mp4" --auto-threshold --preview "D:\촬영\diy_01_미리보기.mp4"
```

끝나면 두 개가 생긴다.
- `diy_01.cuts.json` — 컷·표시 **계획 파일** (프리미어 적용에 사용)
- `diy_01_미리보기.mp4` — **검수용 미리보기 영상**

실행 끝에 이런 요약이 뜬다.
```
✂️  컷 3개 | 270프레임 (9.0s)
🔖 표시 8개 (static 5, offcenter 3)
```

## 4단계. 미리보기로 검수하기

`diy_01_미리보기.mp4`를 그냥 열어서 본다. 화면에 이렇게 표시된다.

- **초록 박스** = 중앙 안전영역(작업물·도구가 이 안에 잘 보이는 게 좋음)
- **흰 점** = 화면 내용(작업물)의 무게중심 위치
- 위쪽 글자 = `motion`(움직임 크기), `center`(중앙에 내용이 모인 정도)
- **노란 테두리 [CUT/MARK] STATIC** = 정지 구간 (3초↑면 CUT, 1.5~3초면 표시)
- **빨간 테두리 [MARK] OFF-CENTER** = 중앙에 작업물·도구가 잘 안 보이는 구간(구도 점검)
- **하늘 테두리 [CUT] STUTTER** = 버벅임

여기서 "이건 잘못 잡았다 / 이건 놓쳤다" 가 보이면 5단계로 미세조정한다.
잘 맞으면 6단계로 넘어간다.

## 5단계. 정확도 미세조정

```powershell
# 우선 이 클립에 맞는 추천값을 본다
python -m pp_autocut "D:\촬영\diy_01.mp4" --auto-threshold --calibrate
```

자주 쓰는 조정:

| 증상 | 해결 |
|------|------|
| 정지를 너무 자주 자른다 | `--static-cut-sec 4` (기준 시간 늘리기) |
| 정지를 아예 안 자르고 싶다 | `--static-cut-sec 999` (표시만) |
| 오프센터(구도)를 너무 많이 잡는다 | `--center-content-thresh 0.2` (낮출수록 덜 민감) |
| 오프센터를 못 잡는다 | `--center-content-thresh 0.4` (높일수록 더 민감) |
| 오프센터 검출이 필요 없다 | `--offcenter-mode off` |

만족스러운 값을 찾으면 `config.example.json`을 복사해 `my.json`으로 저장하고
그 값으로 바꾼 뒤, 다음부터는 이렇게 재사용한다.
```powershell
python -m pp_autocut "D:\촬영\diy_02.mp4" -c my.json --preview "D:\촬영\diy_02_미리보기.mp4"
```

## 6단계. 프리미어에 적용

### 지금(패널 나오기 전) — 반자동/수동

`cuts.json`의 시간 정보를 보고 프리미어에서 직접 처리한다.
JSON의 `remove_ranges`(자를 구간)와 `markers`(표시할 구간)에 각각
`start_tc`(시작 타임코드), `end_tc`(끝 타임코드)가 들어 있다. 예:

```json
"remove_ranges": [
  { "reason": "static", "start_tc": "00:00:12:05", "end_tc": "00:00:16:20" }
],
"markers": [
  { "reason": "offcenter", "start_tc": "00:00:31:10", "end_tc": "00:00:33:00",
    "name": "중앙 피사체 빠짐(구도 점검)" }
]
```

- **표시(markers)**: 해당 타임코드로 재생헤드를 옮기고 `M` 키로 마커를 찍는다.
  검수하면서 직접 자를지 둘지 판단한다.
- **컷(remove_ranges)**: 시작/끝 타임코드에서 `Ctrl+K`(자르기) 후 가운데 클립을
  선택해 `Shift+Delete`(잔물결 삭제)로 제거한다.

> 미리보기 영상을 옆에 띄워두고 같은 타임코드를 맞춰 보면 훨씬 빠르다.

### 다음 단계 — 완전 자동 (프리미어 패널)

`cuts.json`을 읽어 **컷 적용 + 마커 찍기를 버튼 한 번**으로 해주는 프리미어 확장
패널이 다음 작업이다. 완성되면 위 수동 과정이 통째로 사라진다.
설계는 [`panel/README.md`](panel/README.md) 참고.

---

## 자주 막히는 곳

- **`python`을 못 찾는다**: 1단계의 "Add to PATH" 체크를 놓친 것. 파이썬 재설치 또는
  `py -m pp_autocut ...` 로 `py` 런처 사용.
- **`opencv` 설치 오류**: `pip install --upgrade pip` 후 다시 `pip install -r requirements.txt`.
- **경로에 한글/공백**: 경로 전체를 큰따옴표(`"..."`)로 감싸면 된다.
- **세로 영상/다른 fps**: 그대로 동작한다. 결과의 프레임 번호가 1차 기준이라 정확하다.

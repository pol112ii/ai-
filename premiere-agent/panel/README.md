# 프리미어 패널 (다음 단계)

분석부가 만든 `cuts.json`(스키마 `pp-autocut/v1`)을 읽어 현재 시퀀스를 자동 컷하는
프리미어프로 확장 패널 자리다. 아직 구현 전이며, 설계 메모만 둔다.

## 선택한 방식: CEP + ExtendScript

- **CEP 패널(HTML/JS)**: 버튼·진행 상태 등 UI. `cuts.json`을 불러오고, 필요하면
  분석부(Python)를 백그라운드로 실행하도록 호출한다.
- **ExtendScript(.jsx)**: 실제 타임라인 조작. CEP에서 `evalScript`로 호출한다.

## 패널이 할 일 (cuts.json 소비 절차)

`cuts.json`(스키마 `pp-autocut/v2`)에는 **자를 것**과 **표시만 할 것**이 분리돼 있다.

1. `cuts.json`을 읽는다. `fps`, `cut_points`, `remove_ranges`, `markers` 사용.
2. 활성 시퀀스를 가져온다. (QE DOM: `qe.project.getActiveSequence()`)
3. **표시(markers)** 를 먼저 찍는다. 컷으로 프레임 번호가 밀리기 전에 처리하는 편이 안전.
   - 각 마커: `markers[].start_frame/end_frame`, `color`, `name`, `comment`.
   - ExtendScript: `seq.markers.createMarker(start_sec)` → `m.end = end_sec`,
     `m.name = name`, `m.comments = comment`, `m.setColorByIndex(색인)`.
   - 색 이름(`Yellow`/`Red`/`Cyan` …)은 패널에서 색인 번호로 매핑한다.
4. **컷(remove_ranges)** 을 적용한다.
   - `cut_points`의 각 프레임에서 면도날 컷(`razor`). 프레임→초 = `frame / fps`.
   - `remove_ranges`를 **뒤에서 앞 순서로** 리플 삭제한다.
     (앞에서부터 지우면 뒤 구간 프레임 번호가 밀려 어긋난다.)
5. 완료 후 컷 개수·표시 개수를 UI에 표시한다.

> 표시(static/offcenter)는 영상을 자르지 않고 사람이 검수할 위치만 알려준다.
> 자동으로 자르는 것은 버벅임(stutter)뿐이며, 이는 분석부 설정으로 바꿀 수 있다.

> QE DOM API(`qe.*`)는 비공개 인터페이스라 버전에 따라 동작이 다를 수 있다.
> 안정성이 필요하면 공식 `Sequence`/`TrackItem` API와 시퀀스 인/아웃 + 리프트/추출
> 조합으로 대체하는 방안을 검토한다.

## 프레임 기준 주의

`cuts.json`은 프레임 번호를 1차 기준으로 삼는다. 패널에서 시간으로 환산할 때는
반드시 `cuts.json`의 `fps`를 쓰고, 시퀀스 fps와 소스 fps가 다르면 환산을 보정한다.

## 폴더 구조(예정)

```
panel/
├─ CSXS/manifest.xml     # CEP 확장 매니페스트
├─ index.html            # 패널 UI
├─ js/main.js            # UI 로직, cuts.json 로드, evalScript 호출
└─ jsx/autocut.jsx       # 타임라인 컷(razor + ripple delete) + 마커 찍기
```

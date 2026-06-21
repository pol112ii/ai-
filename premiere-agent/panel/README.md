# PP AutoCut 프리미어 패널

`cuts.json`(스키마 `pp-autocut/v2`)을 만들고 활성 시퀀스에 **컷 + 마커를 자동 적용**하는
프리미어프로 CEP 확장 패널입니다.

## 동작 흐름

```
[타임라인에 영상] → 패널 "분석하고 적용" 클릭
   → (1) ExtendScript 로 활성 시퀀스의 소스 영상 경로/오프셋 확보
   → (2) Node 로 파이썬 분석기 실행: python -m pp_autocut <소스> --auto-threshold -o <tmp.json>
   → (3) ExtendScript(ppac_applyPlan)로 시퀀스에 컷(QE razor+ripple) + 마커 적용
```

## 구성

```
panel/
├─ CSXS/manifest.xml   # CEP 확장 매니페스트 (Node 활성화)
├─ .debug              # 미서명 디버깅용
├─ index.html          # 패널 UI
├─ css/style.css
├─ js/CSInterface.js   # 최소 CEP 인터페이스
├─ js/main.js          # UI 로직: 감지→파이썬 실행→적용
├─ jsx/autocut.jsx     # 타임라인 컷(razor+ripple) + 마커 찍기
└─ install.ps1         # Windows 설치 스크립트
```

## 설치 (Windows)

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

이 스크립트가 ① 미서명 확장 허용(`PlayerDebugMode=1`) ② 패널을
`%APPDATA%\Adobe\CEP\extensions\com.joybear.ppautocut` 로 복사
③ `pip install -e`(분석기) 를 한다. 끝나면 프리미어 재시작 후
**창 > 확장 > PP AutoCut** 에서 연다.

## 사용

1. 시퀀스를 만들고 영상을 타임라인(V1)에 올린다.
2. 패널에서 **① 현재 시퀀스 감지** → 소스 영상/ fps 확인.
3. 옵션(정지 컷 기준, 구도 민감도, 컷/마커 적용 여부) 설정.
4. **② 분석하고 적용** → 컷·마커가 자동으로 들어간다.

## 시간 매핑

분석기는 '소스 영상' 기준 초를 준다. 클립이 트림/이동됐을 수 있으므로
`시퀀스초 = clip.start + (소스초 - clip.inPoint)` 로 변환하고, 클립 가시범위
밖은 건너뛴다. 컷을 먼저 적용한 뒤 마커는 잘려나간 길이만큼 보정해 배치한다.

## 주의 / 한계

- **컷은 QE(비공개 API)의 razor + ripple 삭제**를 쓴다. 프리미어 버전에 따라
  동작이 다를 수 있어 각 단계를 try/catch 로 감쌌다. **처음에는 시퀀스 사본에서
  테스트**할 것. 마커는 공식 API라 안정적이다.
- 컷이 적용 안 되면 패널의 **'실제 컷 적용'을 끄고 마커만** 받은 뒤, 마커 위치를
  보며 수동으로 잘라도 된다(검수 워크플로).
- 마커 색 인덱스(`setColorByIndex`)는 버전별 매핑이 다를 수 있다.
- 단일 클립(보통 V1) 기준으로 매핑한다. 여러 클립을 이어붙인 복잡한 시퀀스는
  먼저 한 클립으로 합치거나(중간 렌더) 클립을 선택해 대상으로 지정한다.

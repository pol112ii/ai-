/*
 * PP AutoCut - ExtendScript (Premiere Pro)
 * cuts.json(스키마 pp-autocut/v2)을 읽어 활성 시퀀스에 마커/컷을 적용한다.
 *
 * 시간 매핑: 분석기는 '소스 영상' 기준 초(start_sec/end_sec)를 준다.
 * 시퀀스에 놓인 클립이 트림(inPoint)·이동(start)됐을 수 있으므로
 *   시퀀스초 = 소스초 + (clip.start - clip.inPoint)
 * 로 변환하고, 클립 가시범위 [inPoint, outPoint] 밖은 건너뛴다.
 *
 * 컷은 QE(undocumented) 의 razor + ripple 삭제를 쓴다. 버전에 따라 동작이
 * 다를 수 있어 try/catch 로 감싸며, 마커는 공식 API라 안정적이다.
 */

var PPAC_TICKS_PER_SECOND = 254016000000;
// 사유 -> 마커 색 인덱스 (setColorByIndex; 버전별 매핑 차이 가능)
var PPAC_COLOR = { "static": 1, "offcenter": 0, "stutter": 2 };

function ppac_readFile(path) {
  var f = File(path);
  if (!f.exists) return null;
  f.open("r"); f.encoding = "UTF-8";
  var c = f.read(); f.close();
  return c;
}

function ppac_parse(text) {
  // cuts.json 은 우리가 만든 신뢰 가능한 데이터이므로 eval 로 파싱.
  return eval("(" + text + ")");
}

function ppac_seqFps(seq) {
  return PPAC_TICKS_PER_SECOND / Number(seq.timebase);
}

function ppac_targetClip(seq) {
  var i, j, t;
  // 선택된 비디오 클립 우선
  for (i = 0; i < seq.videoTracks.numTracks; i++) {
    t = seq.videoTracks[i];
    for (j = 0; j < t.clips.numItems; j++) {
      if (t.clips[j].isSelected()) return t.clips[j];
    }
  }
  // 없으면 첫 비디오 클립
  for (i = 0; i < seq.videoTracks.numTracks; i++) {
    t = seq.videoTracks[i];
    if (t.clips.numItems > 0) return t.clips[0];
  }
  return null;
}

function ppac_getContext() {
  var seq = app.project.activeSequence;
  if (!seq) return JSON.stringify({ ok: false, error: "활성 시퀀스가 없습니다. 시퀀스를 열고 영상을 올려주세요." });
  var clip = ppac_targetClip(seq);
  if (!clip) return JSON.stringify({ ok: false, error: "시퀀스에 영상 클립이 없습니다." });
  var media = "";
  try { media = clip.projectItem.getMediaPath(); } catch (e) { media = ""; }
  return JSON.stringify({
    ok: true,
    sequence: seq.name,
    clipName: clip.name,
    media: media,
    fps: ppac_seqFps(seq),
    clipStart: clip.start.seconds,
    clipIn: clip.inPoint.seconds,
    clipOut: clip.outPoint.seconds
  });
}

function ppac_pad(n) { return (n < 10 ? "0" : "") + n; }

function ppac_secToTc(sec, fps) {
  var fpsI = Math.round(fps);
  var f = Math.round(sec * fps);
  var ff = f % fpsI;
  var tot = Math.floor(f / fpsI);
  return ppac_pad(Math.floor(tot / 3600)) + ":" +
    ppac_pad(Math.floor(tot / 60) % 60) + ":" +
    ppac_pad(tot % 60) + ":" + ppac_pad(ff);
}

function ppac_buildRemoves(plan, clipIn, clipOut) {
  // remove_ranges 를 클립 가시범위로 클램프해 {s,e}(소스초) 목록으로. 시작순 정렬.
  var src = plan.remove_ranges || [];
  var out = [];
  for (var i = 0; i < src.length; i++) {
    var s = Math.max(src[i].start_sec, clipIn);
    var e = Math.min(src[i].end_sec, clipOut);
    if (e - s > 0) out.push({ s: s, e: e });
  }
  out.sort(function (a, b) { return a.s - b.s; });
  return out;
}

function ppac_removedBefore(removes, t) {
  // t(소스초) 이전에 잘려나간 총 소스 길이(초). 컷 적용 후 마커 위치 보정용.
  var sum = 0;
  for (var i = 0; i < removes.length; i++) {
    if (removes[i].e <= t) sum += (removes[i].e - removes[i].s);
  }
  return sum;
}

function ppac_applyMarkers(seq, plan, clipStart, clipIn, clipOut, removes, shift) {
  var mk = plan.markers || [];
  var added = 0;
  for (var i = 0; i < mk.length; i++) {
    var m = mk[i];
    if (m.end_sec <= clipIn || m.start_sec >= clipOut) continue; // 가시범위 밖
    var ms = Math.max(m.start_sec, clipIn);
    var me = Math.min(m.end_sec, clipOut);
    var rb = shift ? ppac_removedBefore(removes, ms) : 0; // 컷으로 당겨진 만큼 보정
    var s = clipStart + (ms - clipIn) - rb;
    var e = clipStart + (me - clipIn) - rb;
    try {
      var mar = seq.markers.createMarker(s);
      try { mar.name = m.name || m.reason; } catch (e1) {}
      try { mar.comments = m.comment || ""; } catch (e2) {}
      try { mar.end = e; } catch (e3) {} // 구간 마커(버전에 따라 무시될 수 있음)
      try {
        var ci = PPAC_COLOR[m.reason];
        if (ci !== undefined) mar.setColorByIndex(ci);
      } catch (e4) {}
      added++;
    } catch (eMain) {}
  }
  return added;
}

function ppac_rippleDelete(q, sSeq, eSeq) {
  // 모든 비디오/오디오 트랙에서 [sSeq, eSeq) 안에서 시작하는 아이템을 리플 삭제.
  function sweep(track) {
    for (var k = track.numItems - 1; k >= 0; k--) {
      var it = track.getItemAt(k);
      var st = Number(it.start.secs);
      if (st >= sSeq - 0.0005 && st < eSeq - 0.0005) {
        try { it.remove(true, false); } catch (e) {}
      }
    }
  }
  var t;
  for (t = 0; t < q.numVideoTracks; t++) sweep(q.getVideoTrackAt(t));
  for (t = 0; t < q.numAudioTracks; t++) sweep(q.getAudioTrackAt(t));
}

function ppac_applyCuts(removes, clipStart, clipIn, fps) {
  if (removes.length === 0) return 0;
  app.enableQE();
  var q = qe.project.getActiveSequence();
  var done = 0;
  // 뒤에서 앞으로: 앞 구간을 지워도 뒤 구간 위치가 안 밀리도록.
  for (var i = removes.length - 1; i >= 0; i--) {
    var sSeq = clipStart + (removes[i].s - clipIn);
    var eSeq = clipStart + (removes[i].e - clipIn);
    if (eSeq - sSeq <= 0) continue;
    try {
      q.razor(ppac_secToTc(sSeq, fps));
      q.razor(ppac_secToTc(eSeq, fps));
      ppac_rippleDelete(q, sSeq, eSeq);
      done++;
    } catch (e) {}
  }
  return done;
}

function ppac_applyPlan(jsonPath, doCuts, doMarkers) {
  var seq = app.project.activeSequence;
  if (!seq) return JSON.stringify({ ok: false, error: "활성 시퀀스가 없습니다." });
  var clip = ppac_targetClip(seq);
  if (!clip) return JSON.stringify({ ok: false, error: "시퀀스에 영상 클립이 없습니다." });
  var text = ppac_readFile(jsonPath);
  if (!text) return JSON.stringify({ ok: false, error: "결과 파일을 읽지 못했습니다: " + jsonPath });

  var plan;
  try { plan = ppac_parse(text); } catch (e) { return JSON.stringify({ ok: false, error: "결과 파일 파싱 실패" }); }

  var fps = ppac_seqFps(seq);
  var clipIn = clip.inPoint.seconds;
  var clipOut = clip.outPoint.seconds;
  var clipStart = clip.start.seconds;
  var removes = ppac_buildRemoves(plan, clipIn, clipOut);

  var markers = 0, cuts = 0;
  // 컷을 먼저 적용한 뒤, 마커는 잘려나간 길이만큼 보정해 배치한다.
  if (doCuts) cuts = ppac_applyCuts(removes, clipStart, clipIn, fps);
  if (doMarkers) markers = ppac_applyMarkers(seq, plan, clipStart, clipIn, clipOut, removes, doCuts);

  return JSON.stringify({ ok: true, markers: markers, cuts: cuts });
}

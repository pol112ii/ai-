/* PP AutoCut 패널 로직.
 * 흐름: 시퀀스 감지 -> 소스 영상 경로 확보 -> 파이썬 분석기 실행(cuts.json) ->
 *       ExtendScript(applyPlan)로 시퀀스에 컷/마커 적용.
 */
(function () {
  "use strict";

  var cs = new CSInterface();

  // ---- Node 모듈 (CEP: --enable-nodejs) ----
  var nodeRequire = (typeof require !== "undefined") ? require
    : (typeof cep_node !== "undefined" ? cep_node.require : null);
  var childProcess = nodeRequire ? nodeRequire("child_process") : null;
  var fs = nodeRequire ? nodeRequire("fs") : null;
  var os = nodeRequire ? nodeRequire("os") : null;
  var pathMod = nodeRequire ? nodeRequire("path") : null;

  var $ = function (id) { return document.getElementById(id); };
  var logBox = $("log");
  var lastCtx = null;

  function log(msg, cls) {
    var line = document.createElement("div");
    if (cls) line.className = cls;
    line.textContent = msg;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
  }

  function fwd(p) { return String(p).replace(/\\/g, "/"); }

  // 패널 로드시 ExtendScript 파일 적재
  function loadJsx() {
    var ext = fwd(cs.getSystemPath(SystemPath.EXTENSION));
    cs.evalScript('$.evalFile("' + ext + '/jsx/autocut.jsx")', function () {});
  }

  function detect() {
    cs.evalScript("ppac_getContext()", function (res) {
      var c;
      try { c = JSON.parse(res); } catch (e) { log("감지 응답 파싱 실패: " + res, "err"); return; }
      if (!c.ok) { $("ctx").textContent = "⚠ " + c.error; lastCtx = null; return; }
      lastCtx = c;
      $("ctx").textContent =
        "시퀀스: " + c.sequence + "\n" +
        "클립: " + c.clipName + "\n" +
        "소스: " + c.media + "\n" +
        "fps: " + Number(c.fps).toFixed(2);
    });
  }

  function run() {
    if (!childProcess) {
      log("Node.js 가 활성화되지 않았습니다. (manifest --enable-nodejs 확인)", "err");
      return;
    }
    detect();
    // detect 는 비동기라 잠시 후 진행
    setTimeout(runAfterDetect, 250);
  }

  function runAfterDetect() {
    if (!lastCtx || !lastCtx.media) {
      log("먼저 '① 현재 시퀀스 감지'로 소스 영상을 확인하세요.", "err");
      return;
    }
    var media = lastCtx.media;
    if (!fs.existsSync(media)) {
      log("소스 파일을 찾을 수 없습니다: " + media, "err");
      return;
    }

    var pyCmd = $("pyCmd").value.trim() || "python";
    var out = pathMod.join(os.tmpdir(), "ppac_" + Date.now() + ".cuts.json");

    var args = ["-m", "pp_autocut", media, "--auto-threshold",
      "--static-cut-sec", String(parseFloat($("staticCut").value) || 3.0),
      "--center-content-thresh", String(parseFloat($("centerThresh").value) || 0.30),
      "-o", out, "-q"];
    if (!$("doOffcenter").checked) { args.push("--offcenter-mode", "off"); }

    $("run").disabled = true;
    log("분석 시작… (" + pyCmd + " -m pp_autocut)");

    var proc;
    try {
      proc = childProcess.spawn(pyCmd, args, { windowsHide: true });
    } catch (e) {
      $("run").disabled = false;
      log("파이썬 실행 실패: " + e.message, "err");
      return;
    }

    proc.stderr.on("data", function (d) { log(String(d).trim(), "err"); });
    proc.on("error", function (e) {
      $("run").disabled = false;
      log("파이썬을 실행할 수 없습니다: " + e.message +
        "\n→ 'python 명령'을 'py' 로 바꾸거나, premiere-agent 에서 'pip install -e .' 했는지 확인하세요.", "err");
    });
    proc.on("close", function (code) {
      if (code !== 0) {
        $("run").disabled = false;
        log("분석 실패 (종료코드 " + code + ")", "err");
        return;
      }
      log("분석 완료 → 시퀀스에 적용 중…", "ok");
      applyPlan(out);
    });
  }

  function applyPlan(jsonPath) {
    var doCuts = $("doCuts").checked ? "true" : "false";
    var doMarkers = $("doMarkers").checked ? "true" : "false";
    var script = 'ppac_applyPlan("' + fwd(jsonPath) + '", ' + doCuts + ', ' + doMarkers + ')';
    cs.evalScript(script, function (res) {
      $("run").disabled = false;
      var r;
      try { r = JSON.parse(res); } catch (e) { log("적용 응답 파싱 실패: " + res, "err"); return; }
      if (!r.ok) { log("적용 실패: " + r.error, "err"); return; }
      log("✔ 완료 — 컷 " + r.cuts + "개, 마커 " + r.markers + "개 적용", "ok");
    });
  }

  $("detect").addEventListener("click", detect);
  $("run").addEventListener("click", run);

  loadJsx();
  log("준비됨. 타임라인에 영상을 올린 뒤 ①→② 순서로 진행하세요.");
})();

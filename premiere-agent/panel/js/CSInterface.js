/*
 * 최소 CSInterface 구현 (PP AutoCut 패널 전용).
 * 공식 CEP CSInterface.js 의 일부 기능만 담는다: evalScript, getSystemPath, OS 판별.
 * __adobe_cep__ 전역은 CEP 런타임이 주입한다.
 */
var SystemPath = {
  USER_DATA: "userData",
  COMMON_FILES: "commonFiles",
  MY_DOCUMENTS: "myDocuments",
  APPLICATION: "application",
  EXTENSION: "extension",
  HOST_APPLICATION: "hostApplication"
};

function CSInterface() {}

CSInterface.prototype.getOSInformation = function () {
  var ua = (typeof navigator !== "undefined" && navigator.platform) || "";
  if (ua.indexOf("Win") >= 0) return "Windows";
  if (ua.indexOf("Mac") >= 0) return "Mac";
  return "Other";
};

CSInterface.prototype.evalScript = function (script, callback) {
  if (callback === null || callback === undefined) {
    callback = function () {};
  }
  window.__adobe_cep__.evalScript(script, callback);
};

CSInterface.prototype.getSystemPath = function (pathType) {
  var path = window.__adobe_cep__.getSystemPath(pathType);
  try { path = decodeURIComponent(path); } catch (e) {}
  // file:// 접두 제거
  path = path.replace(/^file:\/{2,3}/, "");
  return path;
};

CSInterface.prototype.getApplicationID = function () {
  var host = JSON.parse(window.__adobe_cep__.getHostEnvironment());
  return host.appName;
};

const BRIDGE = "http://127.0.0.1:8765";

async function bridgePost(path, payload) {
  const response = await fetch(`${BRIDGE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-BSC-DLP-Extension": "1"
    },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`bridge_http_${response.status}${text ? `:${text.trim()}` : ""}`);
  }

  return response.json();
}


const BSC_GUARD_HEARTBEAT_ALARM = "bsc_dlp_guard_heartbeat";
const BSC_GUARD_HEARTBEAT_MINUTES = 1;

function bscBrowserName() {
  const ua = String(navigator.userAgent || "");
  if (/Edg\//i.test(ua)) return "edge";
  if (/Firefox\//i.test(ua)) return "firefox";
  if (/Chrome\//i.test(ua) || /Chromium\//i.test(ua)) return "chrome";
  return "unknown";
}

function bscGetInstallID() {
  return new Promise(resolve => {
    chrome.storage.local.get(["bsc_dlp_install_id"], values => {
      if (chrome.runtime.lastError) {
        resolve("");
        return;
      }
      let value = String(values?.bsc_dlp_install_id || "").trim();
      if (value) {
        resolve(value);
        return;
      }
      value = (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function")
        ? globalThis.crypto.randomUUID()
        : `bsc-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      chrome.storage.local.set({ bsc_dlp_install_id: value }, () => resolve(value));
    });
  });
}

async function bscSendGuardHeartbeat() {
  const browser = bscBrowserName();
  if (browser === "unknown") return;
  const installID = await bscGetInstallID();
  const manifest = chrome.runtime.getManifest();
  await bridgePost("/v1/guard/heartbeat", {
    browser,
    extension_version: String(manifest?.version || ""),
    install_id: installID
  });
}

function bscEnsureHeartbeatAlarm() {
  if (!chrome.alarms || typeof chrome.alarms.create !== "function") return;
  chrome.alarms.create(BSC_GUARD_HEARTBEAT_ALARM, {
    delayInMinutes: 0.5,
    periodInMinutes: BSC_GUARD_HEARTBEAT_MINUTES
  });
}

if (chrome.alarms?.onAlarm) {
  chrome.alarms.onAlarm.addListener(alarm => {
    if (alarm?.name === BSC_GUARD_HEARTBEAT_ALARM) {
      bscSendGuardHeartbeat().catch(() => {});
    }
  });
}

if (chrome.runtime?.onInstalled) {
  chrome.runtime.onInstalled.addListener(() => {
    bscEnsureHeartbeatAlarm();
    bscSendGuardHeartbeat().catch(() => {});
  });
}

if (chrome.runtime?.onStartup) {
  chrome.runtime.onStartup.addListener(() => {
    bscEnsureHeartbeatAlarm();
    bscSendGuardHeartbeat().catch(() => {});
  });
}

bscEnsureHeartbeatAlarm();
bscSendGuardHeartbeat().catch(() => {});


chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message.type !== "string") return;

  let request;

  if (message.type === "bsc_dlp_inspect") {
    request = bridgePost("/v1/inspect", {
      destination: message.destination || "browser",
      page_url: message.page_url || "",
      event_type: message.event_type || "send",
      browser: navigator.userAgent || "browser-extension",
      text: message.text || ""
    });
  } else if (message.type === "bsc_dlp_file_start") {
    request = bridgePost("/v1/upload/start", {
      destination: message.destination || "",
      page_url: message.page_url || "",
      event_type: message.event_type || "file_picker",
      browser: navigator.userAgent || "browser-extension",
      filename: message.filename || "",
      content_type: message.content_type || "",
      size: Number(message.size || 0)
    });
  } else if (message.type === "bsc_dlp_file_chunk") {
    request = bridgePost("/v1/upload/chunk", {
      upload_id: message.upload_id || "",
      sequence: Number(message.sequence || 0),
      data: message.data || ""
    });
  } else if (message.type === "bsc_dlp_file_finish") {
    request = bridgePost("/v1/upload/finish", {
      upload_id: message.upload_id || ""
    });
  } else if (message.type === "bsc_dlp_file_cancel") {
    request = bridgePost("/v1/upload/cancel", {
      upload_id: message.upload_id || ""
    });
  } else {
    return;
  }

  request
    .then(data => sendResponse({ ok: true, data }))
    .catch(error => sendResponse({
      ok: false,
      error: String(error && error.message ? error.message : error)
    }));

  return true;
});

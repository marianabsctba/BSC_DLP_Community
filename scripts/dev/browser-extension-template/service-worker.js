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

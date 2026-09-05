const BRIDGE = "http://127.0.0.1:8765";

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || message.type !== "bsc_dlp_inspect") return;

  const payload = {
    destination: message.destination || "whatsapp_web",
    page_url: message.page_url || "",
    event_type: message.event_type || "send",
    browser: navigator.userAgent || "browser-extension",
    text: message.text || ""
  };

  fetch(`${BRIDGE}/v1/inspect`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-BSC-DLP-Extension": "1"
    },
    body: JSON.stringify(payload)
  })
    .then(async response => {
      if (!response.ok) throw new Error(`bridge_http_${response.status}`);
      return response.json();
    })
    .then(data => sendResponse({ ok: true, data }))
    .catch(error => sendResponse({
      ok: false,
      error: String(error && error.message ? error.message : error)
    }));

  return true;
});

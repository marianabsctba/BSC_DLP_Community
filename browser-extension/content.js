(() => {
  "use strict";

  const DESTINATION = "whatsapp_web";
  let bypassSendOnce = false;

  function toast(message, blocked = false) {
    let box = document.getElementById("bsc-dlp-browser-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "bsc-dlp-browser-toast";
      box.style.position = "fixed";
      box.style.right = "22px";
      box.style.bottom = "22px";
      box.style.zIndex = "2147483647";
      box.style.maxWidth = "380px";
      box.style.padding = "14px 16px";
      box.style.borderRadius = "12px";
      box.style.font = "600 13px/1.45 system-ui, sans-serif";
      box.style.boxShadow = "0 18px 60px rgba(0,0,0,.45)";
      box.style.backdropFilter = "blur(12px)";
      document.documentElement.appendChild(box);
    }

    box.textContent = message;
    box.style.color = "#fff";
    box.style.background = blocked ? "rgba(80, 10, 35, .96)" : "rgba(18, 12, 18, .96)";
    box.style.border = blocked ? "1px solid #ff2d95" : "1px solid #4a3548";
    box.style.display = "block";

    clearTimeout(box.__bscTimer);
    box.__bscTimer = setTimeout(() => { box.style.display = "none"; }, 4200);
  }

  function isComposer(node) {
    if (!(node instanceof Element)) return false;
    const editable = node.closest('[contenteditable="true"]');
    if (!editable) return false;
    return Boolean(editable.closest("footer")) || editable.getAttribute("role") === "textbox";
  }

  function composer() {
    return document.querySelector('footer [contenteditable="true"][role="textbox"]') ||
           document.querySelector('footer [contenteditable="true"]') ||
           document.querySelector('[contenteditable="true"][role="textbox"]');
  }

  function composerText() {
    const c = composer();
    return c ? (c.innerText || c.textContent || "").trim() : "";
  }

  function sendButton() {
    return document.querySelector('button [data-icon="send"]')?.closest("button") ||
           document.querySelector('[data-testid="compose-btn-send"]')?.closest("button") ||
           document.querySelector('button[aria-label="Send"]');
  }

  function inspect(text, eventType) {
    return new Promise(resolve => {
      chrome.runtime.sendMessage({
        type: "bsc_dlp_inspect",
        destination: DESTINATION,
        page_url: location.href,
        event_type: eventType,
        text
      }, response => {
        if (chrome.runtime.lastError || !response || !response.ok) {
          resolve({ available: false, block: false, action: "ALLOW", classifications: [] });
          return;
        }

        const data = response.data || {};
        resolve({
          available: true,
          block: Boolean(data.block),
          action: String(data.action || "ALLOW"),
          classifications: Array.isArray(data.classifications) ? data.classifications : []
        });
      });
    });
  }

  function insertText(target, text) {
    target.focus();

    try {
      if (document.execCommand("insertText", false, text)) return true;
    } catch {}

    const selection = window.getSelection();
    if (!selection) return false;

    let range;
    if (selection.rangeCount) {
      range = selection.getRangeAt(0);
    } else {
      range = document.createRange();
      range.selectNodeContents(target);
      range.collapse(false);
    }

    range.deleteContents();
    const node = document.createTextNode(text);
    range.insertNode(node);
    range.setStartAfter(node);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);

    target.dispatchEvent(new InputEvent("input", {
      bubbles: true,
      inputType: "insertText",
      data: text
    }));
    return true;
  }

  function classificationLabel(list) {
    return list && list.length ? ` (${list.join(", ")})` : "";
  }

  document.addEventListener("paste", async event => {
    if (!isComposer(event.target)) return;

    const text = event.clipboardData?.getData("text/plain") || "";
    if (!text.trim()) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const target = event.target.closest('[contenteditable="true"]') || event.target;
    const result = await inspect(text, "paste");

    if (!result.available) {
      insertText(target, text);
      toast("BSC DLP: agente local indisponível; conteúdo liberado (fail-open).");
      return;
    }

    if (result.block) {
      toast(`BSC DLP bloqueou conteúdo sensível no WhatsApp Web${classificationLabel(result.classifications)}.`, true);
      return;
    }

    insertText(target, text);

    if (result.action === "ALERT") {
      toast(`BSC DLP registrou conteúdo sensível no WhatsApp Web${classificationLabel(result.classifications)}.`);
    }
  }, true);

  document.addEventListener("keydown", async event => {
    if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
    if (!isComposer(event.target)) return;

    const text = composerText();
    if (!text) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const result = await inspect(text, "send_enter");

    if (!result.available) {
      const button = sendButton();
      if (button) {
        bypassSendOnce = true;
        button.click();
      }
      toast("BSC DLP: agente local indisponível; envio liberado (fail-open).");
      return;
    }

    if (result.block) {
      toast(`BSC DLP bloqueou o envio no WhatsApp Web${classificationLabel(result.classifications)}.`, true);
      return;
    }

    const button = sendButton();
    if (button) {
      bypassSendOnce = true;
      button.click();
    }

    if (result.action === "ALERT") {
      toast(`BSC DLP registrou conteúdo sensível no WhatsApp Web${classificationLabel(result.classifications)}.`);
    }
  }, true);

  document.addEventListener("click", async event => {
    const button = event.target instanceof Element ? event.target.closest("button") : null;
    if (!button) return;

    const isSend =
      Boolean(button.querySelector('[data-icon="send"]')) ||
      button.matches('[data-testid="compose-btn-send"]') ||
      button.getAttribute("aria-label") === "Send";

    if (!isSend) return;

    if (bypassSendOnce) {
      bypassSendOnce = false;
      return;
    }

    const text = composerText();
    if (!text) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const result = await inspect(text, "send_click");

    if (!result.available) {
      bypassSendOnce = true;
      button.click();
      toast("BSC DLP: agente local indisponível; envio liberado (fail-open).");
      return;
    }

    if (result.block) {
      toast(`BSC DLP bloqueou o envio no WhatsApp Web${classificationLabel(result.classifications)}.`, true);
      return;
    }

    bypassSendOnce = true;
    button.click();

    if (result.action === "ALERT") {
      toast(`BSC DLP registrou conteúdo sensível no WhatsApp Web${classificationLabel(result.classifications)}.`);
    }
  }, true);

  console.info("[BSC DLP] Browser Guard active on WhatsApp Web");
})();

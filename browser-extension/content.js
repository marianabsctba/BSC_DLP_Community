(() => {
  "use strict";

  const FILE_CHUNK_BYTES = 192 * 1024;
  const WHATSAPP_HOST = "web.whatsapp.com";

  const bypassChange = new WeakSet();
  let replayingDrop = false;
  let replayingPaste = false;
  let bypassSendOnce = false;

  function pageURL() {
    return `${location.origin}${location.pathname}`;
  }

  function uploadDestination() {
    return (location.hostname || "browser").toLowerCase();
  }

  function textDestination() {
    return location.hostname.toLowerCase() === WHATSAPP_HOST
      ? "whatsapp_web"
      : uploadDestination();
  }

  function toast(message, blocked = false) {
    let box = document.getElementById("bsc-dlp-browser-toast");
    if (!box) {
      box = document.createElement("div");
      box.id = "bsc-dlp-browser-toast";
      box.style.position = "fixed";
      box.style.right = "22px";
      box.style.bottom = "22px";
      box.style.zIndex = "2147483647";
      box.style.maxWidth = "430px";
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
    box.__bscTimer = setTimeout(() => { box.style.display = "none"; }, 5200);
  }

  function runtimeMessage(message) {
    return new Promise(resolve => {
      const runtime = globalThis.chrome?.runtime;

      if (!runtime || typeof runtime.sendMessage !== "function") {
        resolve({
          ok: false,
          error: "extension_runtime_unavailable"
        });
        return;
      }

      try {
        runtime.sendMessage(message, response => {
          let runtimeError = null;

          try {
            runtimeError = runtime.lastError?.message || null;
          } catch {}

          if (runtimeError || !response || !response.ok) {
            resolve({
              ok: false,
              error: runtimeError || response?.error || "bridge_unavailable"
            });
            return;
          }

          resolve({
            ok: true,
            data: response.data || {}
          });
        });
      } catch (error) {
        resolve({
          ok: false,
          error: error?.message || "extension_runtime_unavailable"
        });
      }
    });
  }

  function bytesToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = "";
    const step = 0x8000;
    for (let i = 0; i < bytes.length; i += step) {
      const slice = bytes.subarray(i, Math.min(i + step, bytes.length));
      binary += String.fromCharCode(...slice);
    }
    return btoa(binary);
  }

  async function inspectFile(file, eventType) {
    const start = await runtimeMessage({
      type: "bsc_dlp_file_start",
      destination: uploadDestination(),
      page_url: pageURL(),
      event_type: eventType,
      filename: file.name || "upload.bin",
      content_type: file.type || "",
      size: file.size
    });

    if (!start.ok) {
      return { available: false, block: false, action: "ALLOW", classifications: [], reason: start.error };
    }

    if (start.data.skip) {
      return {
        available: true,
        block: false,
        action: String(start.data.action || "ALLOW"),
        classifications: [],
        reason: String(start.data.reason || "not_inspected")
      };
    }

    const uploadID = String(start.data.upload_id || "");
    if (!uploadID) {
      return { available: false, block: false, action: "ALLOW", classifications: [], reason: "missing_upload_id" };
    }

    try {
      let sequence = 0;
      for (let offset = 0; offset < file.size; offset += FILE_CHUNK_BYTES) {
        const part = file.slice(offset, Math.min(offset + FILE_CHUNK_BYTES, file.size));
        const encoded = bytesToBase64(await part.arrayBuffer());

        const chunk = await runtimeMessage({
          type: "bsc_dlp_file_chunk",
          upload_id: uploadID,
          sequence,
          data: encoded
        });

        if (!chunk.ok) {
          throw new Error(chunk.error || "chunk_failed");
        }
        sequence += 1;
      }

      const finish = await runtimeMessage({
        type: "bsc_dlp_file_finish",
        upload_id: uploadID
      });

      if (!finish.ok) {
        throw new Error(finish.error || "finish_failed");
      }

      const data = finish.data || {};
      return {
        available: data.status !== "error",
        block: Boolean(data.block),
        action: String(data.action || "ALLOW"),
        classifications: Array.isArray(data.classifications) ? data.classifications : [],
        reason: String(data.reason || "")
      };
    } catch (error) {
      await runtimeMessage({
        type: "bsc_dlp_file_cancel",
        upload_id: uploadID
      });
      return {
        available: false,
        block: false,
        action: "ALLOW",
        classifications: [],
        reason: String(error && error.message ? error.message : error)
      };
    }
  }

  function actionRank(action) {
    switch (String(action || "").toUpperCase()) {
      case "BLOCK":
      case "QUARANTINE":
        return 3;
      case "ALERT":
        return 2;
      case "AUDIT":
        return 1;
      default:
        return 0;
    }
  }

  async function inspectFiles(files, eventType) {
    const list = Array.from(files || []).filter(Boolean);
    if (!list.length) {
      return { available: true, block: false, action: "ALLOW", classifications: [], reasons: [] };
    }

    let available = true;
    let block = false;
    let action = "ALLOW";
    const classifications = new Set();
    const reasons = [];

    for (const file of list) {
      const result = await inspectFile(file, eventType);
      if (!result.available) available = false;
      if (result.block) block = true;
      if (actionRank(result.action) > actionRank(action)) action = result.action;
      for (const item of result.classifications || []) classifications.add(item);
      if (result.reason) reasons.push(`${file.name}:${result.reason}`);
      if (result.block) break;
    }

    return {
      available,
      block,
      action,
      classifications: [...classifications],
      reasons
    };
  }

  function classificationLabel(list) {
    return list && list.length ? ` (${list.join(", ")})` : "";
  }

  function skippedInspectionLabel(reasons) {
    const reason = (reasons || []).find(item =>
      item.includes("file_too_large") || item.includes("unsupported_file_type") || item.includes("inspection_error")
    );
    return reason ? ` BSC DLP nÃ£o inspecionou completamente: ${reason}.` : "";
  }

  function replayFileInput(input) {
    bypassChange.add(input);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
  }

  document.addEventListener("change", async event => {
    const input = event.target instanceof HTMLInputElement ? event.target : null;
    if (!input || input.type !== "file") return;

    if (bypassChange.has(input)) {
      bypassChange.delete(input);
      return;
    }

    const files = input.files;
    if (!files || !files.length) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const result = await inspectFiles(files, "file_picker");

    if (!result.available) {
      replayFileInput(input);
      toast("BSC DLP: agente local indisponÃ­vel; upload liberado (fail-open).");
      return;
    }

    if (result.block) {
      input.value = "";
      toast(
        `BSC DLP bloqueou arquivo sensÃ­vel antes do upload para ${uploadDestination()}${classificationLabel(result.classifications)}.`,
        true
      );
      return;
    }

    replayFileInput(input);

    if (result.action === "ALERT") {
      toast(
        `BSC DLP registrou conteÃºdo sensÃ­vel em upload para ${uploadDestination()}${classificationLabel(result.classifications)}.`
      );
    } else {
      const skipped = skippedInspectionLabel(result.reasons);
      if (skipped) toast(skipped.trim());
    }
  }, true);

  document.addEventListener("drop", async event => {
    if (replayingDrop) return;

    const files = event.dataTransfer?.files;
    if (!files || !files.length) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const target = event.target;
    const originalFiles = Array.from(files);
    const result = await inspectFiles(originalFiles, "drag_drop");

    if (!result.available) {
      toast("BSC DLP: agente local indisponÃ­vel; upload por drag & drop liberado (fail-open).");
    } else if (result.block) {
      toast(
        `BSC DLP bloqueou arquivo sensÃ­vel em drag & drop para ${uploadDestination()}${classificationLabel(result.classifications)}.`,
        true
      );
      return;
    } else if (result.action === "ALERT") {
      toast(
        `BSC DLP registrou conteÃºdo sensÃ­vel em drag & drop para ${uploadDestination()}${classificationLabel(result.classifications)}.`
      );
    }

    try {
      const transfer = new DataTransfer();
      for (const file of originalFiles) transfer.items.add(file);
      const replay = new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer: transfer
      });
      replayingDrop = true;
      target.dispatchEvent(replay);
    } finally {
      replayingDrop = false;
    }
  }, true);

  document.addEventListener("paste", async event => {
    if (replayingPaste) return;

    const files = event.clipboardData?.files;
    if (!files || !files.length) return;

    event.preventDefault();
    event.stopImmediatePropagation();

    const target = event.target;
    const originalFiles = Array.from(files);
    const result = await inspectFiles(originalFiles, "paste_file");

    if (!result.available) {
      toast("BSC DLP: agente local indisponÃ­vel; colagem de arquivo liberada (fail-open).");
    } else if (result.block) {
      toast(
        `BSC DLP bloqueou arquivo/imagem sensÃ­vel colado em ${uploadDestination()}${classificationLabel(result.classifications)}.`,
        true
      );
      return;
    } else if (result.action === "ALERT") {
      toast(
        `BSC DLP registrou arquivo/imagem sensÃ­vel colado em ${uploadDestination()}${classificationLabel(result.classifications)}.`
      );
    }

    try {
      const transfer = new DataTransfer();
      for (const file of originalFiles) transfer.items.add(file);
      const replay = new ClipboardEvent("paste", {
        bubbles: true,
        cancelable: true,
        clipboardData: transfer
      });
      replayingPaste = true;
      target.dispatchEvent(replay);
    } finally {
      replayingPaste = false;
    }
  }, true);

  // Existing WhatsApp Web outgoing text guard remains active, but only there.
  if (false && location.hostname.toLowerCase() === WHATSAPP_HOST) {
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

    function inspectText(text, eventType) {
      return runtimeMessage({
        type: "bsc_dlp_inspect",
        destination: textDestination(),
        page_url: pageURL(),
        event_type: eventType,
        text
      }).then(result => {
        if (!result.ok) {
          return {
            available: false,
            block: false,
            action: "ALLOW",
            classifications: []
          };
        }

        const data = result.data || {};

        return {
          available: true,
          block: Boolean(data.block),
          action: String(data.action || "ALLOW"),
          classifications: Array.isArray(data.classifications)
            ? data.classifications
            : []
        };
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

    document.addEventListener("paste", async event => {
      if (!isComposer(event.target)) return;
      if (event.clipboardData?.files?.length) return;

      const text = event.clipboardData?.getData("text/plain") || "";
      if (!text.trim()) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      const target = event.target.closest('[contenteditable="true"]') || event.target;
      const result = await inspectText(text, "paste");

      if (!result.available) {
        insertText(target, text);
        toast("BSC DLP: agente local indisponÃ­vel; conteÃºdo liberado (fail-open).");
        return;
      }

      if (result.block) {
        toast(`BSC DLP bloqueou conteÃºdo sensÃ­vel no WhatsApp Web${classificationLabel(result.classifications)}.`, true);
        return;
      }

      insertText(target, text);
      if (result.action === "ALERT") {
        toast(`BSC DLP registrou conteÃºdo sensÃ­vel no WhatsApp Web${classificationLabel(result.classifications)}.`);
      }
    }, true);

    document.addEventListener("keydown", async event => {
      if (event.key !== "Enter" || event.shiftKey || event.ctrlKey || event.altKey || event.metaKey) return;
      if (!isComposer(event.target)) return;

      const text = composerText();
      if (!text) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      const result = await inspectText(text, "send_enter");

      if (!result.available) {
        const button = sendButton();
        if (button) {
          bypassSendOnce = true;
          button.click();
        }
        toast("BSC DLP: agente local indisponÃ­vel; envio liberado (fail-open).");
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
        toast(`BSC DLP registrou conteÃºdo sensÃ­vel no WhatsApp Web${classificationLabel(result.classifications)}.`);
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

      const result = await inspectText(text, "send_click");

      if (!result.available) {
        bypassSendOnce = true;
        button.click();
        toast("BSC DLP: agente local indisponÃ­vel; envio liberado (fail-open).");
        return;
      }

      if (result.block) {
        toast(`BSC DLP bloqueou o envio no WhatsApp Web${classificationLabel(result.classifications)}.`, true);
        return;
      }

      bypassSendOnce = true;
      button.click();

      if (result.action === "ALERT") {
        toast(`BSC DLP registrou conteÃºdo sensÃ­vel no WhatsApp Web${classificationLabel(result.classifications)}.`);
      }
    }, true);
  }

  console.info(`[BSC DLP] Browser Guard v0.6.7 active: generic upload DLP on ${uploadDestination()}`);
})();


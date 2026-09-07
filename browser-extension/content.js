(() => {
  "use strict";

  const FILE_CHUNK_BYTES = 192 * 1024;
  const WHATSAPP_HOST = "web.whatsapp.com";
  const AI_SITES = [
    {
      host: "chatgpt.com",
      provider: "openai",
      destination: "chatgpt"
    },
    {
      host: "chat.openai.com",
      provider: "openai",
      destination: "chatgpt"
    },
    {
      host: "claude.ai",
      provider: "anthropic",
      destination: "claude"
    },
    {
      host: "gemini.google.com",
      provider: "google",
      destination: "gemini"
    },
    {
      host: "copilot.microsoft.com",
      provider: "microsoft",
      destination: "copilot"
    }
  ];

  function aiSiteForHost(hostname = location.hostname) {
    const host = String(hostname || "").trim().toLowerCase();

    for (const site of AI_SITES) {
      if (host === site.host || host.endsWith(`.${site.host}`)) {
        return site;
      }
    }

    return null;
  }

  function isAIDestination() {
    return Boolean(aiSiteForHost());
  }

  function aiDestination() {
    return aiSiteForHost()?.destination || "";
  }

  function aiProvider() {
    return aiSiteForHost()?.provider || "";
  }

  let aiSendBypass = false;
  let aiInspectionPending = false;

  function visibleElement(node) {
    if (!(node instanceof Element)) return false;
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0;
  }

  function chatGPTComposer() {
    const selectors = [
      "#prompt-textarea",
      'textarea[data-testid="prompt-textarea"]',
      '[contenteditable="true"][data-testid="prompt-textarea"]',
      '[contenteditable="true"][role="textbox"]',
      "textarea"
    ];

    for (const selector of selectors) {
      const nodes = document.querySelectorAll(selector);

      for (const node of nodes) {
        if (visibleElement(node)) return node;
      }
    }

    return null;
  }

  function composerValue(node) {
    if (!node) return "";

    if (node instanceof HTMLTextAreaElement ||
        node instanceof HTMLInputElement) {
      return String(node.value || "").trim();
    }

    return String(node.innerText || node.textContent || "").trim();
  }

  function chatGPTSendButton() {
    const selectors = [
      'button[data-testid="send-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send"]',
      'button[aria-label="Enviar prompt"]',
      'button[aria-label="Enviar"]'
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);

      if (button instanceof HTMLButtonElement &&
          visibleElement(button)) {
        return button;
      }
    }

    const composer = chatGPTComposer();
    const form = composer?.closest("form");

    if (form) {
      const submit = form.querySelector('button[type="submit"]');

      if (submit instanceof HTMLButtonElement &&
          visibleElement(submit)) {
        return submit;
      }
    }

    return null;
  }

  function isChatGPTComposerTarget(node) {
    const composer = chatGPTComposer();

    if (!composer || !(node instanceof Node)) return false;

    return node === composer ||
      (composer instanceof Element && composer.contains(node));
  }

  async function inspectAIPrompt(text, eventType) {
    const result = await runtimeMessage({
      type: "bsc_dlp_inspect",
      destination: aiDestination(),
      page_url: pageURL(),
      event_type: eventType,
      channel: "ai_prompt",
      provider: aiProvider(),
      text
    });

    if (!result.ok) {
      return {
        available: false,
        block: false,
        action: "ALLOW",
        classifications: [],
        reason: result.error || "bridge_unavailable"
      };
    }

    const data = result.data || {};

    return {
      available: true,
      block: Boolean(data.block),
      action: String(data.action || "ALLOW").toUpperCase(),
      classifications: Array.isArray(data.classifications)
        ? data.classifications
        : [],
      reason: String(data.reason || "")
    };
  }

  async function guardChatGPTPrompt(eventType, replaySend) {
    if (aiInspectionPending) return;

    const composer = chatGPTComposer();
    const text = composerValue(composer);

    if (!text) {
      replaySend();
      return;
    }

    aiInspectionPending = true;

    try {
      const result = await inspectAIPrompt(text, eventType);

      if (!result.available) {
        toast(
          "BSC DLP AI Gateway: agente local indispon?vel; prompt liberado (fail-open)."
        );

        replaySend();
        return;
      }

      if (result.block) {
        toast(
          `BSC DLP AI Gateway bloqueou o envio do prompt para ChatGPT${classificationLabel(result.classifications)}.`,
          true
        );
        return;
      }

      if (result.action === "ALERT") {
        toast(
          `BSC DLP AI Gateway detectou conte?do sens?vel no prompt para ChatGPT${classificationLabel(result.classifications)}.`
        );
      }

      replaySend();
    } finally {
      aiInspectionPending = false;
    }
  }

  function replayChatGPTSend(button) {
    if (!(button instanceof HTMLButtonElement)) return;

    aiSendBypass = true;
    button.click();
  }

  if (aiDestination() === "chatgpt") {

    document.addEventListener("click", async event => {
      const clicked = event.target instanceof Element
        ? event.target.closest("button")
        : null;

      if (!(clicked instanceof HTMLButtonElement)) return;

      if (aiSendBypass) {
        aiSendBypass = false;
        return;
      }

      const send = chatGPTSendButton();

      if (!send || clicked !== send) return;

      const prompt = composerValue(chatGPTComposer());
      if (!prompt) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardChatGPTPrompt(
        "prompt_submit_click",
        () => replayChatGPTSend(send)
      );
    }, true);


    document.addEventListener("keydown", async event => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.isComposing) return;

      if (!isChatGPTComposerTarget(event.target)) return;

      const prompt = composerValue(chatGPTComposer());
      if (!prompt) return;

      const send = chatGPTSendButton();

      // Sem bot?o confi?vel, n?o impedimos o site de funcionar.
      if (!send || send.disabled) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardChatGPTPrompt(
        "prompt_submit_enter",
        () => replayChatGPTSend(send)
      );
    }, true);
  }



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

  // WhatsApp Web outgoing text guard.
  // Normal clipboard/editing shortcuts are never intercepted.
  if (location.hostname.toLowerCase() === WHATSAPP_HOST) {

    function isComposer(node) {
      if (!(node instanceof Element)) return false;

      const editable = node.closest('[contenteditable="true"]');
      if (!editable) return false;

      return Boolean(editable.closest("footer")) ||
             editable.getAttribute("role") === "textbox";
    }

    function composer() {
      return document.querySelector(
        'footer [contenteditable="true"][role="textbox"]'
      ) ||
      document.querySelector(
        'footer [contenteditable="true"]'
      ) ||
      document.querySelector(
        '[contenteditable="true"][role="textbox"]'
      );
    }

    function composerText() {
      const node = composer();

      return node
        ? String(node.innerText || node.textContent || "").trim()
        : "";
    }

    function sendButton() {
      return (
        document.querySelector(
          'button [data-icon="send"]'
        )?.closest("button") ||

        document.querySelector(
          '[data-testid="compose-btn-send"]'
        )?.closest("button") ||

        document.querySelector(
          'button[aria-label="Send"]'
        ) ||

        document.querySelector(
          'button[aria-label="Enviar"]'
        )
      );
    }

    async function inspectWhatsAppText(text, eventType) {
      const result = await runtimeMessage({
        type: "bsc_dlp_inspect",
        destination: "whatsapp_web",
        page_url: pageURL(),
        event_type: eventType,
        channel: "messaging",
        text
      });

      if (!result.ok) {
        return {
          available: false,
          block: false,
          action: "ALLOW",
          classifications: [],
          reason: result.error || "bridge_unavailable"
        };
      }

      const data = result.data || {};

      return {
        available: true,
        block: Boolean(data.block),
        action: String(data.action || "ALLOW").toUpperCase(),
        classifications: Array.isArray(data.classifications)
          ? data.classifications
          : [],
        reason: String(data.reason || "")
      };
    }

    function replayWhatsAppSend(button) {
      if (!(button instanceof HTMLElement)) return false;

      bypassSendOnce = true;
      button.click();

      return true;
    }

    async function guardWhatsAppSend(eventType, button) {
      const text = composerText();

      if (!text) {
        return;
      }

      const result = await inspectWhatsAppText(
        text,
        eventType
      );

      if (!result.available) {
        replayWhatsAppSend(button);

        toast(
          "BSC DLP: agente local indisponível; envio no WhatsApp liberado (fail-open)."
        );

        return;
      }

      if (result.block) {
        toast(
          `BSC DLP bloqueou o envio no WhatsApp Web${classificationLabel(result.classifications)}.`,
          true
        );

        return;
      }

      replayWhatsAppSend(button);

      if (result.action === "ALERT") {
        toast(
          `BSC DLP registrou conteúdo sensível no WhatsApp Web${classificationLabel(result.classifications)}.`
        );
      }
    }

    // -------------------------------------------------------
    // ENTER
    //
    // IMPORTANTE:
    // Ctrl / Alt / Meta / Shift jamais sao bloqueados aqui.
    // -------------------------------------------------------

    document.addEventListener("keydown", async event => {

      if (event.key !== "Enter") return;

      if (
        event.shiftKey ||
        event.ctrlKey ||
        event.altKey ||
        event.metaKey ||
        event.isComposing
      ) {
        return;
      }

      if (!isComposer(event.target)) {
        return;
      }

      const text = composerText();
      if (!text) return;

      const button = sendButton();

      // Se nao conseguimos identificar com seguranca o botao,
      // deixamos o WhatsApp funcionar normalmente.
      if (!button) {
        return;
      }

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardWhatsAppSend(
        "send_enter",
        button
      );

    }, true);

    // -------------------------------------------------------
    // CLICK NO SEND
    // -------------------------------------------------------

    document.addEventListener("click", async event => {

      const button =
        event.target instanceof Element
          ? event.target.closest("button")
          : null;

      if (!button) return;

      const isSend =
        Boolean(
          button.querySelector('[data-icon="send"]')
        ) ||
        button.matches(
          '[data-testid="compose-btn-send"]'
        ) ||
        button.getAttribute("aria-label") === "Send" ||
        button.getAttribute("aria-label") === "Enviar";

      if (!isSend) return;

      if (bypassSendOnce) {
        bypassSendOnce = false;
        return;
      }

      const text = composerText();
      if (!text) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardWhatsAppSend(
        "send_click",
        button
      );

    }, true);
  }

  // ==========================================================
  // BSC_EMAIL_WEB_GUARD
  // Gmail + Outlook Web outgoing message inspection
  // ==========================================================

  const EMAIL_SITES = [
    {
      hosts: ["mail.google.com"],
      provider: "gmail",
      destination: "gmail"
    },
    {
      hosts: [
        "outlook.office.com",
        "outlook.office365.com",
        "outlook.live.com"
      ],
      provider: "outlook",
      destination: "outlook_web"
    }
  ];

  function emailSiteForHost(hostname = location.hostname) {
    const host = String(hostname || "").toLowerCase();

    for (const site of EMAIL_SITES) {
      if (site.hosts.some(item => host === item || host.endsWith(`.${item}`))) {
        return site;
      }
    }

    return null;
  }

  const emailSite = emailSiteForHost();
  const emailReplayBypass = new WeakSet();
  let emailInspectionPending = false;

  function visibleEmailElement(node) {
    if (!(node instanceof Element)) return false;

    const rect = node.getBoundingClientRect();

    return rect.width > 0 &&
      rect.height > 0 &&
      getComputedStyle(node).visibility !== "hidden";
  }

  function gmailSendButtonFromTarget(target) {
    if (!(target instanceof Element)) return null;

    const candidate = target.closest(
      '[role="button"][data-tooltip^="Send"],' +
      '[role="button"][data-tooltip^="Enviar"],' +
      '[role="button"][aria-label^="Send"],' +
      '[role="button"][aria-label^="Enviar"]'
    );

    return candidate && visibleEmailElement(candidate)
      ? candidate
      : null;
  }

  function outlookSendButtonFromTarget(target) {
    if (!(target instanceof Element)) return null;

    const candidate = target.closest(
      'button[aria-label^="Send"],' +
      'button[aria-label^="Enviar"],' +
      '[role="button"][aria-label^="Send"],' +
      '[role="button"][aria-label^="Enviar"],' +
      'button[title^="Send"],' +
      'button[title^="Enviar"]'
    );

    return candidate && visibleEmailElement(candidate)
      ? candidate
      : null;
  }

  function emailSendButtonFromTarget(target) {
    if (!emailSite) return null;

    if (emailSite.provider === "gmail") {
      return gmailSendButtonFromTarget(target);
    }

    if (emailSite.provider === "outlook") {
      return outlookSendButtonFromTarget(target);
    }

    return null;
  }

  function gmailComposeRoot(sendButton) {
    return sendButton?.closest('[role="dialog"]') ||
      sendButton?.closest('div[aria-label*="Message" i]') ||
      document;
  }

  function outlookComposeRoot(sendButton) {
    return sendButton?.closest('[role="dialog"]') ||
      sendButton?.closest('[data-app-section]') ||
      document;
  }

  function firstVisibleIn(root, selectors) {
    for (const selector of selectors) {
      const nodes = root.querySelectorAll(selector);

      for (const node of nodes) {
        if (visibleEmailElement(node)) {
          return node;
        }
      }
    }

    return null;
  }

  function gmailMessageText(sendButton) {
    const root = gmailComposeRoot(sendButton);

    const subject = firstVisibleIn(root, [
      'input[name="subjectbox"]',
      'input[placeholder*="Subject" i]',
      'input[aria-label*="Subject" i]',
      'input[placeholder*="Assunto" i]',
      'input[aria-label*="Assunto" i]'
    ]);

    const body = firstVisibleIn(root, [
      '[aria-label="Message Body"][contenteditable="true"]',
      '[aria-label*="Message Body" i][contenteditable="true"]',
      '[aria-label*="Corpo" i][contenteditable="true"]',
      '[role="textbox"][contenteditable="true"]'
    ]);

    const subjectText = subject instanceof HTMLInputElement
      ? String(subject.value || "").trim()
      : "";

    const bodyText = composerValue(body);

    return [subjectText, bodyText]
      .filter(Boolean)
      .join("\n\n");
  }

  function outlookMessageText(sendButton) {
    const root = outlookComposeRoot(sendButton);

    const subject = firstVisibleIn(root, [
      'input[placeholder*="Add a subject" i]',
      'input[aria-label*="subject" i]',
      'input[placeholder*="assunto" i]',
      'input[aria-label*="assunto" i]'
    ]);

    const body = firstVisibleIn(root, [
      '[aria-label*="Message body" i][contenteditable="true"]',
      '[aria-label*="Corpo da mensagem" i][contenteditable="true"]',
      '[role="textbox"][contenteditable="true"]'
    ]);

    const subjectText = subject instanceof HTMLInputElement
      ? String(subject.value || "").trim()
      : "";

    const bodyText = composerValue(body);

    return [subjectText, bodyText]
      .filter(Boolean)
      .join("\n\n");
  }

  function emailMessageText(sendButton) {
    if (!emailSite) return "";

    if (emailSite.provider === "gmail") {
      return gmailMessageText(sendButton);
    }

    if (emailSite.provider === "outlook") {
      return outlookMessageText(sendButton);
    }

    return "";
  }

  async function inspectEmailMessage(text, eventType) {
    const result = await runtimeMessage({
      type: "bsc_dlp_inspect",
      destination: emailSite?.destination || "webmail",
      page_url: pageURL(),
      event_type: eventType,
      channel: "email",
      text
    });

    if (!result.ok) {
      return {
        available: false,
        block: false,
        action: "ALLOW",
        classifications: [],
        reason: result.error || "bridge_unavailable"
      };
    }

    const data = result.data || {};

    return {
      available: true,
      block: Boolean(data.block),
      action: String(data.action || "ALLOW").toUpperCase(),
      classifications: Array.isArray(data.classifications)
        ? data.classifications
        : [],
      reason: String(data.reason || "")
    };
  }

  function replayEmailSend(sendButton) {
    if (!(sendButton instanceof Element)) return;

    emailReplayBypass.add(sendButton);
    sendButton.click();
  }

  async function guardEmailSend(sendButton) {
    if (emailInspectionPending) return;

    const text = emailMessageText(sendButton);

    if (!text) {
      replayEmailSend(sendButton);
      return;
    }

    emailInspectionPending = true;

    try {
      const result = await inspectEmailMessage(
        text,
        "email_send_click"
      );

      if (!result.available) {
        toast(
          "BSC DLP Email Guard: agente local indisponivel; envio liberado (fail-open)."
        );

        replayEmailSend(sendButton);
        return;
      }

      if (result.block) {
        toast(
          `BSC DLP bloqueou o envio do email${classificationLabel(result.classifications)}.`,
          true
        );
        return;
      }

      if (result.action === "ALERT") {
        toast(
          `BSC DLP detectou conteudo sensivel no email${classificationLabel(result.classifications)}.`
        );
      }

      replayEmailSend(sendButton);
    } finally {
      emailInspectionPending = false;
    }
  }

  if (emailSite) {
    document.addEventListener("click", async event => {
      const sendButton = emailSendButtonFromTarget(event.target);

      if (!sendButton) return;

      if (emailReplayBypass.has(sendButton)) {
        emailReplayBypass.delete(sendButton);
        return;
      }

      const text = emailMessageText(sendButton);

      if (!text) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardEmailSend(sendButton);
    }, true);
  }
  console.info(`[BSC DLP] Browser Guard v0.6.7 active: generic upload DLP on ${uploadDestination()}`);

  // ==========================================================
  // AI Gateway - Claude adapter
  // ==========================================================

  function claudeComposer() {
    const selectors = [
      '[data-testid="chat-input"][contenteditable="true"]',
      '[data-testid="chat-input"] [contenteditable="true"]',
      'div.tiptap.ProseMirror[contenteditable="true"]',
      '.ProseMirror.remirror-editor[contenteditable="true"]',
      '.ProseMirror[contenteditable="true"]',
      '[contenteditable="true"][role="textbox"]'
    ];

    for (const selector of selectors) {
      const nodes = document.querySelectorAll(selector);

      for (const node of nodes) {
        if (visibleElement(node)) {
          return node;
        }
      }
    }

    return null;
  }


  function claudeSendButton() {
    const composer = claudeComposer();
    const form = composer?.closest("form");

    const selectors = [
      'button[data-testid="send-button"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Send Message"]',
      'button[aria-label="Send"]',
      'button[aria-label="Enviar"]',
      'button[aria-label*="send" i]',
      'button[aria-label*="enviar" i]',
      'button[type="submit"]'
    ];

    const roots = [];

    if (form) roots.push(form);
    roots.push(document);

    for (const root of roots) {
      for (const selector of selectors) {
        const buttons = root.querySelectorAll(selector);

        for (const button of buttons) {
          if (button instanceof HTMLButtonElement &&
              visibleElement(button) &&
              !button.disabled &&
              button.getAttribute("aria-disabled") !== "true") {
            return button;
          }
        }
      }
    }

    return null;
  }


  function isClaudeComposerTarget(node) {
    const composer = claudeComposer();

    if (!composer || !(node instanceof Node)) return false;

    return node === composer ||
      (composer instanceof Element && composer.contains(node));
  }


  let claudeSubmitBypass = false;

  function replayClaudeSend(button) {
    if (!(button instanceof HTMLButtonElement)) return;

    aiSendBypass = true;
    claudeSubmitBypass = true;
    button.click();
  }


  async function guardClaudePrompt(eventType, replaySend) {
    if (aiInspectionPending) return;

    const composer = claudeComposer();
    const text = composerValue(composer);

    if (!text) {
      replaySend();
      return;
    }

    aiInspectionPending = true;

    try {
      const result = await inspectAIPrompt(text, eventType);

      if (!result.available) {
        toast(
          "BSC DLP AI Gateway: agente local indispon?vel; prompt liberado (fail-open)."
        );

        replaySend();
        return;
      }

      if (result.block) {
        toast(
          `BSC DLP AI Gateway bloqueou o envio do prompt para Claude${classificationLabel(result.classifications)}.`,
          true
        );
        return;
      }

      if (result.action === "ALERT") {
        toast(
          `BSC DLP AI Gateway detectou conte?do sens?vel no prompt para Claude${classificationLabel(result.classifications)}.`
        );
      }

      replaySend();

    } finally {
      aiInspectionPending = false;
    }
  }


  if (aiDestination() === "claude") {

    document.addEventListener("submit", async event => {
      if (!(event.target instanceof HTMLFormElement)) return;

      const composer = claudeComposer();
      if (!composer || !event.target.contains(composer)) return;

      if (claudeSubmitBypass) {
        claudeSubmitBypass = false;
        return;
      }

      const prompt = composerValue(composer);
      if (!prompt) return;

      const send = claudeSendButton();
      if (!send) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardClaudePrompt(
        "prompt_submit_form",
        () => replayClaudeSend(send)
      );
    }, true);


    document.addEventListener("click", async event => {
      const clicked = event.target instanceof Element
        ? event.target.closest("button")
        : null;

      if (!(clicked instanceof HTMLButtonElement)) return;

      if (aiSendBypass) {
        aiSendBypass = false;
        return;
      }

      const composer = claudeComposer();
      if (!composer) return;

      const form = composer.closest("form");
      const send = claudeSendButton();

      const label = String(clicked.getAttribute("aria-label") || "").toLowerCase();

      const looksLikeSend =
        clicked === send ||
        Boolean(
          form &&
          form.contains(clicked) &&
          (
            clicked.type === "submit" ||
            label.includes("send") ||
            label.includes("enviar")
          )
        );

      if (!looksLikeSend) return;

      const prompt = composerValue(composer);
      if (!prompt) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardClaudePrompt(
        "prompt_submit_click",
        () => replayClaudeSend(clicked)
      );

    }, true);


    document.addEventListener("keydown", async event => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.isComposing) return;

      if (!isClaudeComposerTarget(event.target)) return;

      const prompt = composerValue(claudeComposer());

      if (!prompt) return;

      const send = claudeSendButton();

      if (!send || send.disabled) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardClaudePrompt(
        "prompt_submit_enter",
        () => replayClaudeSend(send)
      );

    }, true);
  }


  // ==========================================================
  // AI Gateway - Gemini adapter
  // ==========================================================

  function geminiComposer() {
    const selectors = [
      '.ql-editor.textarea[contenteditable="true"]',
      '.ql-editor[contenteditable="true"]',
      'rich-textarea [contenteditable="true"]',
      '[aria-label="Enter a prompt here"][contenteditable="true"]',
      '[contenteditable="true"][role="textbox"]'
    ];

    for (const selector of selectors) {
      const nodes = document.querySelectorAll(selector);

      for (const node of nodes) {
        if (!visibleElement(node)) continue;

        const rect = node.getBoundingClientRect();

        if (rect.width < 200 || rect.height < 20) continue;

        return node;
      }
    }

    return null;
  }


  function geminiSendButton() {
    const composer = geminiComposer();
    const form = composer?.closest("form");

    const selectors = [
      'button[aria-label="Send message"]',
      'button[aria-label*="Send" i]',
      'button[aria-label*="Enviar" i]',
      'button[mattooltip*="Send" i]',
      'button.send-button',
      '.send-button button',
      'button[type="submit"]'
    ];

    const roots = [];

    if (form) roots.push(form);

    if (composer?.parentElement) {
      roots.push(composer.parentElement);

      if (composer.parentElement.parentElement) {
        roots.push(composer.parentElement.parentElement);
      }

      if (composer.parentElement.parentElement?.parentElement) {
        roots.push(composer.parentElement.parentElement.parentElement);
      }
    }

    roots.push(document);

    for (const root of roots) {
      for (const selector of selectors) {
        const buttons = root.querySelectorAll(selector);

        for (const button of buttons) {
          if (button instanceof HTMLButtonElement &&
              visibleElement(button) &&
              !button.disabled &&
              button.getAttribute("aria-disabled") !== "true") {
            return button;
          }
        }
      }
    }

    return null;
  }


  function isGeminiComposerTarget(node) {
    const composer = geminiComposer();

    if (!composer || !(node instanceof Node)) return false;

    return node === composer ||
      (composer instanceof Element && composer.contains(node));
  }


  let geminiSubmitBypass = false;

  function replayGeminiSend(button) {
    if (!(button instanceof HTMLButtonElement)) return;

    aiSendBypass = true;
    geminiSubmitBypass = true;

    try {
      button.click();
    } finally {
      geminiSubmitBypass = false;
    }
  }


  async function guardGeminiPrompt(eventType, replaySend) {
    if (aiInspectionPending) return;

    const composer = geminiComposer();
    const text = composerValue(composer);

    if (!text) {
      replaySend();
      return;
    }

    aiInspectionPending = true;

    try {
      const result = await inspectAIPrompt(text, eventType);

      if (!result.available) {
        toast(
          "BSC DLP AI Gateway: agente local indispon?vel; prompt liberado (fail-open)."
        );

        replaySend();
        return;
      }

      if (result.block) {
        toast(
          `BSC DLP AI Gateway bloqueou o envio do prompt para Gemini${classificationLabel(result.classifications)}.`,
          true
        );
        return;
      }

      if (result.action === "ALERT") {
        toast(
          `BSC DLP AI Gateway detectou conte?do sens?vel no prompt para Gemini${classificationLabel(result.classifications)}.`
        );
      }

      replaySend();

    } finally {
      aiInspectionPending = false;
    }
  }


  if (aiDestination() === "gemini") {

    document.addEventListener("submit", async event => {
      if (!(event.target instanceof HTMLFormElement)) return;

      const composer = geminiComposer();

      if (!composer || !event.target.contains(composer)) return;

      if (geminiSubmitBypass) return;

      const prompt = composerValue(composer);
      if (!prompt) return;

      const send = geminiSendButton();
      if (!send) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardGeminiPrompt(
        "prompt_submit_form",
        () => replayGeminiSend(send)
      );

    }, true);


    document.addEventListener("click", async event => {
      const clicked = event.target instanceof Element
        ? event.target.closest("button")
        : null;

      if (!(clicked instanceof HTMLButtonElement)) return;

      if (aiSendBypass) {
        aiSendBypass = false;
        return;
      }

      const composer = geminiComposer();
      if (!composer) return;

      const send = geminiSendButton();

      const label = String(
        clicked.getAttribute("aria-label") || ""
      ).toLowerCase();

      const tooltip = String(
        clicked.getAttribute("mattooltip") || ""
      ).toLowerCase();

      const looksLikeSend =
        clicked === send ||
        label.includes("send") ||
        label.includes("enviar") ||
        tooltip.includes("send");

      if (!looksLikeSend) return;

      const prompt = composerValue(composer);
      if (!prompt) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardGeminiPrompt(
        "prompt_submit_click",
        () => replayGeminiSend(clicked)
      );

    }, true);


    document.addEventListener("keydown", async event => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.isComposing) return;

      if (!isGeminiComposerTarget(event.target)) return;

      const prompt = composerValue(geminiComposer());
      if (!prompt) return;

      const send = geminiSendButton();

      // Sem bot?o confi?vel, n?o quebramos o funcionamento do Gemini.
      if (!send || send.disabled) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardGeminiPrompt(
        "prompt_submit_enter",
        () => replayGeminiSend(send)
      );

    }, true);
  }


  // ==========================================================
  // AI Gateway - Microsoft Copilot adapter
  // ==========================================================

  function copilotComposer() {
    const selectors = [
      "textarea#userInput",
      'textarea[placeholder="Message Copilot"]',
      'textarea[placeholder*="Copilot" i]',
      'textarea[placeholder*="Ask" i]',
      'textarea[aria-label*="Copilot" i]',
      'textarea',
      '[contenteditable="true"][role="textbox"]'
    ];

    for (const selector of selectors) {
      const nodes = document.querySelectorAll(selector);

      for (const node of nodes) {
        if (!visibleElement(node)) continue;

        const rect = node.getBoundingClientRect();

        if (rect.width < 200 || rect.height < 20) continue;

        return node;
      }
    }

    return null;
  }


  function copilotSendButton() {
    const composer = copilotComposer();
    const form = composer?.closest("form");

    const selectors = [
      'button[aria-label="Submit message"]',
      'button[aria-label*="Submit message" i]',
      'button[aria-label*="Send" i]',
      'button[aria-label*="Enviar" i]',
      'button[data-testid="send-button"]',
      'button[type="submit"]'
    ];

    const roots = [];

    if (form) roots.push(form);

    if (composer?.parentElement) {
      roots.push(composer.parentElement);

      if (composer.parentElement.parentElement) {
        roots.push(composer.parentElement.parentElement);
      }

      if (composer.parentElement.parentElement?.parentElement) {
        roots.push(composer.parentElement.parentElement.parentElement);
      }
    }

    roots.push(document);

    for (const root of roots) {
      for (const selector of selectors) {
        const buttons = root.querySelectorAll(selector);

        for (const button of buttons) {
          if (button instanceof HTMLButtonElement &&
              visibleElement(button) &&
              !button.disabled &&
              button.getAttribute("aria-disabled") !== "true") {
            return button;
          }
        }
      }
    }

    return null;
  }


  function isCopilotComposerTarget(node) {
    const composer = copilotComposer();

    if (!composer || !(node instanceof Node)) return false;

    return node === composer ||
      (composer instanceof Element && composer.contains(node));
  }


  let copilotSubmitBypass = false;

  function replayCopilotSend(button) {
    if (!(button instanceof HTMLButtonElement)) return;

    aiSendBypass = true;
    copilotSubmitBypass = true;

    try {
      button.click();
    } finally {
      copilotSubmitBypass = false;
    }
  }


  async function guardCopilotPrompt(eventType, replaySend) {
    if (aiInspectionPending) return;

    const composer = copilotComposer();
    const text = composerValue(composer);

    if (!text) {
      replaySend();
      return;
    }

    aiInspectionPending = true;

    try {
      const result = await inspectAIPrompt(text, eventType);

      if (!result.available) {
        toast(
          "BSC DLP AI Gateway: agente local indispon?vel; prompt liberado (fail-open)."
        );

        replaySend();
        return;
      }

      if (result.block) {
        toast(
          `BSC DLP AI Gateway bloqueou o envio do prompt para Copilot${classificationLabel(result.classifications)}.`,
          true
        );
        return;
      }

      if (result.action === "ALERT") {
        toast(
          `BSC DLP AI Gateway detectou conte?do sens?vel no prompt para Copilot${classificationLabel(result.classifications)}.`
        );
      }

      replaySend();

    } finally {
      aiInspectionPending = false;
    }
  }


  if (aiDestination() === "copilot") {

    document.addEventListener("submit", async event => {
      if (!(event.target instanceof HTMLFormElement)) return;

      const composer = copilotComposer();

      if (!composer || !event.target.contains(composer)) return;

      if (copilotSubmitBypass) return;

      const prompt = composerValue(composer);
      if (!prompt) return;

      const send = copilotSendButton();
      if (!send) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardCopilotPrompt(
        "prompt_submit_form",
        () => replayCopilotSend(send)
      );

    }, true);


    document.addEventListener("click", async event => {
      const clicked = event.target instanceof Element
        ? event.target.closest("button")
        : null;

      if (!(clicked instanceof HTMLButtonElement)) return;

      if (aiSendBypass) {
        aiSendBypass = false;
        return;
      }

      const composer = copilotComposer();
      if (!composer) return;

      const send = copilotSendButton();

      const label = String(
        clicked.getAttribute("aria-label") || ""
      ).toLowerCase();

      const looksLikeSend =
        clicked === send ||
        label.includes("submit message") ||
        label.includes("send") ||
        label.includes("enviar") ||
        clicked.type === "submit";

      if (!looksLikeSend) return;

      const prompt = composerValue(composer);
      if (!prompt) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardCopilotPrompt(
        "prompt_submit_click",
        () => replayCopilotSend(clicked)
      );

    }, true);


    document.addEventListener("keydown", async event => {
      if (event.key !== "Enter") return;
      if (event.shiftKey) return;
      if (event.ctrlKey || event.altKey || event.metaKey) return;
      if (event.isComposing) return;

      if (!isCopilotComposerTarget(event.target)) return;

      const prompt = composerValue(copilotComposer());
      if (!prompt) return;

      const send = copilotSendButton();

      if (!send || send.disabled) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      await guardCopilotPrompt(
        "prompt_submit_enter",
        () => replayCopilotSend(send)
      );

    }, true);
  }

})();


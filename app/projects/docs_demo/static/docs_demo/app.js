/**
 * Docs Demo — frontend logic
 * Editor, slash commands, comments, command pill
 */
(function () {
  "use strict";

  const pageContent = document.getElementById("docs-demo-page-content");
  const commandInput = document.getElementById("docs-demo-command-input");
  const commandPill = document.getElementById("docs-demo-command-pill");
  const commandPillWrapper = document.getElementById(
    "docs-demo-command-pill-wrapper",
  );
  const commentsGutter = document.getElementById("docs-demo-comments-gutter");
  const geminiBtn = document.getElementById("docs-demo-gemini-btn");
  const errorEl = document.getElementById("docs-demo-error");
  const spinnerEl = document.getElementById("docs-demo-spinner");
  const wordCountEl = document.getElementById("docs-demo-word-count");

  let savedSelection = null;
  let savedSelectionText = "";

  const SLASH_COMMANDS = {
    "/improve": {
      label: "Polish and clarify",
      prompt:
        "Rewrite the following text to be clearer, more concise, and more professional. Return only the improved text, no explanation:\n\n{text}",
      requiresSelection: false,
      type: "text",
    },
    "/expand": {
      label: "Add detail, elaborate",
      prompt:
        "Elaborate on the following text with more detail and supporting points. Return only the expanded text, no explanation:\n\n{text}",
      requiresSelection: false,
      type: "text",
    },
    "/summarize": {
      label: "Condense to summary",
      prompt:
        "Condense the following text into a shorter summary. Return only the summary, no explanation:\n\n{text}",
      requiresSelection: false,
      type: "text",
    },
    "/brainstorm": {
      label: "Bullet-point ideas",
      prompt:
        "Generate exactly 3 to 5 bullet-point ideas about the following topic. Return only the bullet list (use - for each item), no intro text, no explanation, no extra items:\n\n{text}",
      requiresSelection: true,
      type: "text",
    },
    "/review": {
      label: "Passage-level feedback",
      type: "comments",
      requiresSelection: false,
    },
    "/comment": {
      label: "e.g. /comment look for passive voice",
      type: "comments",
      requiresSelection: false,
      requiresExtraText: true,
    },
  };

  /* ----- Document helpers ----- */
  function getDocumentText() {
    return pageContent && pageContent.innerText
      ? pageContent.innerText.trim()
      : "";
  }

  function getSelectionOrFullDocument() {
    if (!pageContent) return "";
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      const range = sel.getRangeAt(0);
      if (pageContent.contains(range.commonAncestorContainer)) {
        const text = range.toString().trim();
        if (text) return text;
      }
    }
    return getDocumentText();
  }

  function updateWordCount() {
    if (!wordCountEl) return;
    const text = getDocumentText();
    const words = text ? text.split(/\s+/).length : 0;
    wordCountEl.textContent = words + (words === 1 ? " word" : " words");
  }

  /* ----- Title: select on first click ----- */
  const titleEl = document.querySelector(".docs-demo-doc-title");
  if (titleEl) {
    let firstClick = true;
    titleEl.addEventListener("focus", function () {
      if (firstClick) {
        const range = document.createRange();
        range.selectNodeContents(this);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        firstClick = false;
      }
    });
  }

  /* ----- Page content: clear placeholder on focus ----- */
  if (pageContent) {
    pageContent.addEventListener("focus", function () {
      if (this.textContent.trim() === "Start typing here...") {
        this.innerHTML = "<p><br></p>";
      }
    });
    pageContent.addEventListener("input", updateWordCount);
    pageContent.addEventListener("paste", function () {
      setTimeout(updateWordCount, 0);
    });
  }

  /* ----- Gemini sparkle: toggle command pill visibility ----- */
  if (geminiBtn && commandPillWrapper) {
    let pillVisible = true;
    geminiBtn.addEventListener("click", function () {
      pillVisible = !pillVisible;
      commandPillWrapper.style.display = pillVisible ? "flex" : "none";
    });
  }

  /* ----- Save selection + show visual indicator when pill gets focus ----- */
  let selectionMarkerSpan = null;

  function clearSelectionMarker() {
    if (selectionMarkerSpan && selectionMarkerSpan.parentNode) {
      const parent = selectionMarkerSpan.parentNode;
      while (selectionMarkerSpan.firstChild) {
        parent.insertBefore(
          selectionMarkerSpan.firstChild,
          selectionMarkerSpan,
        );
      }
      parent.removeChild(selectionMarkerSpan);
    }
    selectionMarkerSpan = null;
  }

  function applySelectionMarker(range) {
    clearSelectionMarker();
    if (!range || range.collapsed) return;
    try {
      selectionMarkerSpan = document.createElement("span");
      selectionMarkerSpan.className = "docs-demo-pill-selection";
      range.surroundContents(selectionMarkerSpan);
    } catch (e) {
      // surroundContents fails for cross-element ranges; fall back to no marker
      selectionMarkerSpan = null;
    }
  }

  function captureDocSelection() {
    const sel = window.getSelection();
    if (
      sel &&
      sel.rangeCount > 0 &&
      pageContent &&
      pageContent.contains(sel.anchorNode)
    ) {
      const range = sel.getRangeAt(0).cloneRange();
      savedSelectionText = range.toString().trim();
      savedSelection = range;
      applySelectionMarker(range.cloneRange());
    }
  }

  if (commandPillWrapper) {
    commandPillWrapper.addEventListener("mousedown", captureDocSelection);
  }

  if (commandInput) {
    commandInput.addEventListener("focus", function () {
      this.select();
    });
  }

  if (pageContent) {
    pageContent.addEventListener("mousedown", clearSelectionMarker);
  }

  /* ----- Apply text result: replace selection or full doc ----- */
  function applyTextResult(text, isBrainstorm, hadSelection) {
    if (!pageContent) return;
    const bulletItems = text.split(/\n/).filter(function (line) {
      const t = line.trim();
      return t && (t.startsWith("-") || t.startsWith("*") || /^\d+\./.test(t));
    });
    const hasBullets = bulletItems.length > 0;

    if (isBrainstorm && hasBullets) {
      const ul = document.createElement("ul");
      bulletItems.forEach(function (item) {
        const cleaned = item.replace(/^[-*]\s*|\d+\.\s*/, "").trim();
        if (cleaned) {
          const li = document.createElement("li");
          li.textContent = cleaned;
          ul.appendChild(li);
        }
      });
      // Insert after the selection marker span if it exists, otherwise after savedSelection
      if (selectionMarkerSpan && selectionMarkerSpan.parentNode) {
        selectionMarkerSpan.parentNode.insertBefore(
          ul,
          selectionMarkerSpan.nextSibling,
        );
      } else if (
        savedSelection &&
        pageContent.contains(savedSelection.commonAncestorContainer)
      ) {
        const range = savedSelection.cloneRange();
        range.collapse(false);
        range.insertNode(ul);
      } else {
        pageContent.appendChild(ul);
      }
    } else if (
      hadSelection &&
      savedSelection &&
      pageContent.contains(savedSelection.commonAncestorContainer)
    ) {
      savedSelection.deleteContents();
      const lines = text.split("\n");
      if (lines.length <= 1) {
        savedSelection.insertNode(document.createTextNode(text));
      } else {
        const frag = document.createDocumentFragment();
        lines.forEach(function (line, i) {
          if (i > 0) frag.appendChild(document.createElement("br"));
          frag.appendChild(document.createTextNode(line));
        });
        savedSelection.insertNode(frag);
      }
    } else {
      replaceFullDocument(text);
    }
    savedSelection = null;
    savedSelectionText = "";
    clearSelectionMarker();
    if (wordCountEl) {
      const docText = (pageContent.innerText || "").trim();
      const words = docText ? docText.split(/\s+/).length : 0;
      wordCountEl.textContent = words + (words === 1 ? " word" : " words");
    }
  }

  function replaceFullDocument(text) {
    if (!pageContent) return;
    const lines = text.split("\n");
    if (lines.length <= 1) {
      pageContent.innerHTML = "<p>" + escapeHtml(text) + "</p>";
    } else {
      pageContent.innerHTML = lines
        .map(function (l) {
          return "<p>" + escapeHtml(l) + "</p>";
        })
        .join("");
    }
  }

  function escapeHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  /* ----- Submit: parse input, call API, apply result ----- */
  function handleSubmit() {
    const raw =
      commandInput && commandInput.value ? commandInput.value.trim() : "";
    if (!raw) return;

    window.docsDemo.hideError();

    if (raw.startsWith("/")) {
      const parts = raw.split(/\s+/);
      const cmd = parts[0];
      const extra = parts.slice(1).join(" ");
      const def = SLASH_COMMANDS[cmd];

      if (cmd === "/review" || cmd === "/comment") {
        handleCommentsCommand(cmd, extra);
        return;
      }

      if (!def) {
        window.docsDemo.showError("Unknown command. Type / for a list.");
        return;
      }

      const selectedText = savedSelectionText;
      let text = selectedText || getDocumentText();
      if (!text) {
        window.docsDemo.showError("Document is empty.");
        return;
      }
      if (def.requiresSelection && !selectedText) {
        window.docsDemo.showError("Please select text to brainstorm about.");
        return;
      }

      const prompt = def.prompt.replace(/{text}/g, text);
      callGenerateText(prompt, text, cmd === "/brainstorm", !!selectedText);
    } else {
      const selectedText = savedSelectionText;
      const text = selectedText || getDocumentText();
      if (!text) {
        window.docsDemo.showError("Document is empty.");
        return;
      }
      callGenerateText(raw, text, false, !!selectedText);
    }
  }

  function handleCommentsCommand(cmd, extra) {
    if (cmd === "/comment" && !extra) {
      window.docsDemo.showError(
        "Please add instructions, e.g. /comment look for passive voice",
      );
      return;
    }
    if (getDocumentText().length === 0) {
      window.docsDemo.showError("Document is empty.");
      return;
    }
    callGenerateComments(cmd, extra);
  }

  function callGenerateText(prompt, text, isBrainstorm, hadSelection) {
    window.docsDemo.setLoading(true);
    fetch(
      typeof API_BASE !== "undefined" ? API_BASE : "/docs-demo/api/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "text", prompt: prompt, text: text }),
      },
    )
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        const result = data.result || "";
        applyTextResult(result, isBrainstorm, hadSelection);
      })
      .catch(function (err) {
        window.docsDemo.showError(
          err.message || "Something went wrong. Please try again.",
        );
      })
      .finally(function () {
        window.docsDemo.setLoading(false);
      });
  }

  function callGenerateComments(cmd, extra) {
    window.docsDemo.setLoading(true);
    const docText = getDocumentText();
    const reviewPrompt =
      'You are a writing editor. Review this document and provide passage-level feedback. Return a JSON array of 2 to 4 objects (no more than 4), each with "target" (exact quote from the document) and "comment" (your feedback). Quote the target text exactly as it appears. Keep each comment to 1-2 sentences. Example: [{"target":"exact phrase","comment":"Brief feedback here."}]';
    const commentPrompt = extra
      ? 'You are a writing editor. The user wants you to look for: "' +
        extra +
        '". Read the document and add comments where appropriate. Return a JSON array of objects with "target" (exact quote) and "comment". Quote targets exactly. Keep each comment to 1-2 sentences.'
      : reviewPrompt;
    const prompt = commentPrompt + "\n\nDocument to review:";

    fetch(
      typeof API_BASE !== "undefined" ? API_BASE : "/docs-demo/api/generate",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "comments",
          prompt: prompt,
          text: docText,
        }),
      },
    )
      .then(function (r) {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        renderComments(data.comments || []);
      })
      .catch(function (err) {
        window.docsDemo.showError(
          err.message || "Something went wrong. Please try again.",
        );
      })
      .finally(function () {
        window.docsDemo.setLoading(false);
      });
  }

  function normalizeWS(str) {
    return str.replace(/\s+/g, " ").trim();
  }

  function renderComments(comments) {
    if (!commentsGutter) return;
    commentsGutter.innerHTML = "";
    if (comments.length === 0) return;

    const docText = getDocumentText();
    const normDocText = normalizeWS(docText);
    const highlights = [];
    let id = 0;

    comments.forEach(function (c) {
      const target = (c.target || "").trim();
      const comment = (c.comment || "").trim();
      if (!target || !comment) return;

      // Try exact match, then whitespace-normalized match
      let idx = docText.indexOf(target);
      let matchedTarget = target;
      if (idx < 0) {
        const normTarget = normalizeWS(target);
        const normIdx = normDocText.indexOf(normTarget);
        if (normIdx < 0) return; // truly not found
        idx = normIdx;
        matchedTarget = normTarget;
      }

      const span = document.createElement("span");
      span.className = "docs-demo-comment-card";
      span.dataset.commentId = String(id);
      span.innerHTML =
        '<div class="docs-demo-comment-body"><div class="docs-demo-comment-text">' +
        escapeHtml(comment) +
        '</div><button class="docs-demo-resolve-btn" title="Resolve comment" aria-label="Resolve">&#10003;</button></div>';
      commentsGutter.appendChild(span);

      span
        .querySelector(".docs-demo-resolve-btn")
        .addEventListener("click", function (e) {
          e.stopPropagation();
          const cid = span.dataset.commentId;
          pageContent
            .querySelectorAll(
              '.docs-demo-comment-highlight[data-comment-id="' + cid + '"]',
            )
            .forEach(function (hl) {
              const parent = hl.parentNode;
              while (hl.firstChild) parent.insertBefore(hl.firstChild, hl);
              parent.removeChild(hl);
            });
          span.remove();
        });

      highlights.push({ target: matchedTarget, idx: idx, id: id });
      id++;
    });

    highlights.sort(function (a, b) {
      return a.idx - b.idx;
    });
    applyHighlights(highlights);
    bindCommentClicks(highlights);
  }

  function buildTextMap() {
    const walker = document.createTreeWalker(
      pageContent,
      NodeFilter.SHOW_TEXT,
      null,
      false,
    );
    const textNodes = [];
    let node;
    while ((node = walker.nextNode())) textNodes.push(node);

    let fullText = "";
    const map = [];
    textNodes.forEach(function (n) {
      const start = fullText.length;
      fullText += n.textContent;
      map.push({ node: n, start: start, end: fullText.length });
    });
    return { fullText: fullText, map: map };
  }

  function applyHighlights(highlights) {
    if (!pageContent || highlights.length === 0) return;

    highlights.sort(function (a, b) {
      return b.idx - a.idx;
    });
    highlights.forEach(function (h) {
      const data = buildTextMap();
      const fullText = data.fullText;
      const map = data.map;

      // Search with normalized whitespace since innerText and textContent diverge at block boundaries
      const normFull = normalizeWS(fullText);
      const normTarget = normalizeWS(h.target);
      let idx = normFull.indexOf(normTarget);
      if (idx < 0) return;

      // Map normalized index back to raw fullText index by counting non-collapsed chars
      let rawIdx = 0;
      let normPos = 0;
      let wsCollapsed = false;
      for (let i = 0; i < fullText.length && normPos < idx; i++) {
        if (/\s/.test(fullText[i])) {
          if (!wsCollapsed) {
            normPos++;
            wsCollapsed = true;
          }
        } else {
          normPos++;
          wsCollapsed = false;
        }
        rawIdx = i + 1;
      }

      // Find actual end in raw text by matching normalized length
      let rawEnd = rawIdx;
      let normLen = 0;
      wsCollapsed = false;
      for (
        let i = rawIdx;
        i < fullText.length && normLen < normTarget.length;
        i++
      ) {
        if (/\s/.test(fullText[i])) {
          if (!wsCollapsed) {
            normLen++;
            wsCollapsed = true;
          }
        } else {
          normLen++;
          wsCollapsed = false;
        }
        rawEnd = i + 1;
      }

      const end = rawEnd;

      for (let i = 0; i < map.length; i++) {
        const m = map[i];
        if (end <= m.start || idx >= m.end) continue;
        const overlapStart = Math.max(idx, m.start);
        const overlapEnd = Math.min(end, m.end);
        if (overlapStart >= overlapEnd) continue;

        const span = document.createElement("span");
        span.className = "docs-demo-comment-highlight";
        span.dataset.commentId = String(h.id);

        const before = m.node.textContent.substring(0, overlapStart - m.start);
        const middle = m.node.textContent.substring(
          overlapStart - m.start,
          overlapEnd - m.start,
        );
        const after = m.node.textContent.substring(overlapEnd - m.start);

        const parent = m.node.parentNode;
        if (!parent) continue;
        const beforeNode = before ? document.createTextNode(before) : null;
        const afterNode = after ? document.createTextNode(after) : null;
        span.textContent = middle;

        if (beforeNode) parent.insertBefore(beforeNode, m.node);
        parent.insertBefore(span, m.node);
        if (afterNode) parent.insertBefore(afterNode, m.node);
        parent.removeChild(m.node);
        return;
      }
    });
  }

  function bindCommentClicks(highlights) {
    if (!pageContent) return;
    function activateComment(id) {
      commentsGutter
        .querySelectorAll(".docs-demo-comment-card")
        .forEach(function (c) {
          c.classList.remove("docs-demo-active");
        });
      pageContent
        .querySelectorAll(".docs-demo-comment-highlight")
        .forEach(function (h) {
          h.classList.remove("docs-demo-active");
        });
      const card = commentsGutter.querySelector(
        '.docs-demo-comment-card[data-comment-id="' + id + '"]',
      );
      if (card) {
        card.classList.add("docs-demo-active");
        card.scrollIntoView({ block: "nearest" });
      }
      pageContent
        .querySelectorAll(
          '.docs-demo-comment-highlight[data-comment-id="' + id + '"]',
        )
        .forEach(function (h) {
          h.classList.add("docs-demo-active");
        });
    }

    pageContent
      .querySelectorAll(".docs-demo-comment-highlight")
      .forEach(function (hl) {
        hl.addEventListener("click", function () {
          activateComment(hl.dataset.commentId);
        });
      });
    commentsGutter
      .querySelectorAll(".docs-demo-comment-card")
      .forEach(function (card) {
        card.addEventListener("click", function () {
          const id = card.dataset.commentId;
          const hl = pageContent.querySelector(
            '.docs-demo-comment-highlight[data-comment-id="' + id + '"]',
          );
          if (hl) hl.scrollIntoView({ block: "center" });
          activateComment(id);
        });
      });
  }

  const autocompleteEl = document.getElementById("docs-demo-autocomplete");
  const helpBtn = document.getElementById("docs-demo-help-btn");
  const sendBtn = document.getElementById("docs-demo-send-btn");

  let autocompleteFilteredCommands = [];
  let autocompleteSelectedIndex = 0;

  function selectAutocompleteItem(cmd) {
    if (commandInput) {
      commandInput.value =
        cmd +
        (SLASH_COMMANDS[cmd] && SLASH_COMMANDS[cmd].requiresExtraText
          ? " "
          : "");
      commandInput.focus();
    }
    autocompleteEl.classList.remove("docs-demo-visible");
  }

  function updateAutocompleteSelection() {
    if (!autocompleteEl) return;
    const items = autocompleteEl.querySelectorAll(
      ".docs-demo-autocomplete-item",
    );
    items.forEach(function (el, i) {
      el.classList.toggle(
        "docs-demo-selected",
        i === autocompleteSelectedIndex,
      );
    });
    const selected = items[autocompleteSelectedIndex];
    if (selected) selected.scrollIntoView({ block: "nearest" });
  }

  function showAutocomplete(filter) {
    if (!autocompleteEl) return;
    const cmdList = Object.keys(SLASH_COMMANDS);
    autocompleteFilteredCommands = !filter
      ? cmdList
      : cmdList.filter(function (c) {
          return (
            c.indexOf(filter) === 0 ||
            c.replace("/", "").indexOf(filter.replace("/", "")) === 0
          );
        });
    if (autocompleteFilteredCommands.length === 0) {
      autocompleteEl.classList.remove("docs-demo-visible");
      return;
    }
    autocompleteSelectedIndex = 0;
    autocompleteEl.innerHTML = autocompleteFilteredCommands
      .map(function (cmd) {
        const def = SLASH_COMMANDS[cmd];
        const label = def ? def.label : cmd;
        return (
          '<div class="docs-demo-autocomplete-item" data-cmd="' +
          escapeHtml(cmd) +
          '">' +
          escapeHtml(cmd) +
          " <span>" +
          escapeHtml(label) +
          "</span></div>"
        );
      })
      .join("");
    autocompleteEl.classList.add("docs-demo-visible");
    autocompleteEl
      .querySelectorAll(".docs-demo-autocomplete-item")
      .forEach(function (el) {
        el.addEventListener("click", function () {
          selectAutocompleteItem(el.dataset.cmd);
        });
      });
    updateAutocompleteSelection();
  }

  function hideAutocomplete() {
    if (autocompleteEl) autocompleteEl.classList.remove("docs-demo-visible");
  }

  if (commandInput) {
    commandInput.addEventListener("input", function () {
      const v = this.value;
      if (v.startsWith("/")) {
        showAutocomplete(v);
      } else {
        hideAutocomplete();
      }
    });
    commandInput.addEventListener("keydown", function (e) {
      const menuOpen =
        autocompleteEl &&
        autocompleteEl.classList.contains("docs-demo-visible");

      if (menuOpen) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          autocompleteSelectedIndex =
            (autocompleteSelectedIndex + 1) %
            autocompleteFilteredCommands.length;
          updateAutocompleteSelection();
          return;
        }
        if (e.key === "ArrowUp") {
          e.preventDefault();
          autocompleteSelectedIndex = autocompleteSelectedIndex - 1;
          if (autocompleteSelectedIndex < 0)
            autocompleteSelectedIndex = autocompleteFilteredCommands.length - 1;
          updateAutocompleteSelection();
          return;
        }
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const cmd = autocompleteFilteredCommands[autocompleteSelectedIndex];
          if (cmd) selectAutocompleteItem(cmd);
          return;
        }
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        hideAutocomplete();
        handleSubmit();
      }
      if (e.key === "Escape") hideAutocomplete();
    });
    commandInput.addEventListener("blur", function () {
      setTimeout(hideAutocomplete, 200);
    });
  }

  if (sendBtn) {
    sendBtn.addEventListener('click', function () {
      hideAutocomplete();
      handleSubmit();
    });
  }

  if (helpBtn) {
    helpBtn.addEventListener("click", function () {
      function getSelectionLabel(d) {
        if (d.requiresSelection) return "Selection required";
        if (d.type === "comments") return "Full document";
        return "Selection or full doc";
      }
      const popup = document.createElement("div");
      popup.className = "docs-demo-help-popup";
      popup.style.cssText =
        "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;border:1px solid #dadce0;border-radius:12px;padding:16px 20px;box-shadow:0 4px 20px rgba(0,0,0,0.2);z-index:1000;max-width:480px;";
      const tableRows = Object.keys(SLASH_COMMANDS)
        .map(function (cmd) {
          const d = SLASH_COMMANDS[cmd];
          let code = d.requiresExtraText ? cmd + " <instructions>" : cmd;
          const label = d.label || cmd;
          const selLabel = getSelectionLabel(d);
          return (
            '<tr><td class="docs-demo-help-cmd"><code>' +
            escapeHtml(code) +
            '</code></td><td class="docs-demo-help-desc">' +
            escapeHtml(label) +
            '</td><td class="docs-demo-help-sel">' +
            escapeHtml(selLabel) +
            "</td></tr>"
          );
        })
        .join("");
      popup.innerHTML =
        '<div class="docs-demo-help-title">Commands</div>' +
        '<table class="docs-demo-help-table"><thead><tr><th>Command</th><th>Description</th><th>Operates on</th></tr></thead><tbody>' +
        tableRows +
        "</tbody></table>";
      const overlay = document.createElement("div");
      overlay.style.cssText =
        "position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:999;";
      overlay.addEventListener("click", function () {
        document.body.removeChild(overlay);
        document.body.removeChild(popup);
      });
      document.body.appendChild(overlay);
      document.body.appendChild(popup);
    });
  }

  /* ----- Expose for later phases ----- */
  window.docsDemo = {
    getDocumentText,
    getSelectionOrFullDocument,
    pageContent,
    commandInput,
    commandPill,
    commentsGutter,
    errorEl,
    showError: function (msg) {
      if (errorEl) {
        errorEl.textContent = msg;
        errorEl.style.display = "block";
      }
    },
    hideError: function () {
      if (errorEl) {
        errorEl.textContent = "";
        errorEl.style.display = "none";
      }
    },
    setLoading: function (loading) {
      if (commandPill) {
        commandPill.classList.toggle("docs-demo-loading", !!loading);
      }
      if (commandInput) {
        commandInput.disabled = !!loading;
      }
      if (spinnerEl) {
        spinnerEl.style.display = loading ? "block" : "none";
      }
    },
  };

  /* ----- About modal & sample text ----- */

  const SAMPLE_TEXTS = {
    "Fake student writing": [
      "<p>The American Civil War was a very important event in history. It happened a long time ago and affected a lot of people. Many soldiers fought in the war and some of them died. Abraham Lincoln was the president at the time and he did a lot of things to help the country. The war was about slavery and also about states rights. In the end the north won and slavery was abolished. This was a good thing because slavery is bad and people should be free. After the war the country had to be rebuilt which was called Reconstruction. Overall the Civil War changed America in many ways and we still feel the effects of it today.</p>",
      "<p>In my opinion social media has both good and bad effects on teenagers. On one hand it lets people stay connected with friends and family and share things about their life. You can also learn new things and see whats happening in the world. On the other hand social media can be really bad for mental health because people compare themselves to others and feel bad about themselves. Also there is a lot of cyberbullying which is when people are mean to each other online. Another problem is that teenagers spend to much time on their phones instead of doing homework or being outside. In conclusion I think social media can be good or bad depending on how you use it and parents should help their kids use it responsibly.</p>",
    ],
    "About soccer": [
      "<p>Soccer, known as football outside the United States, is the world's most widely played sport with an estimated 4 billion fans globally. The game is played between two teams of eleven players on a rectangular grass or artificial turf field, with the objective of scoring goals by getting the ball into the opposing team's net. Unlike many other sports, soccer requires minimal equipment — just a ball and something to mark the goals — which has contributed to its popularity across vastly different economic contexts.</p><p>The sport's pinnacle event, the FIFA World Cup, is held every four years and consistently draws the largest television audiences of any sporting event on the planet. Club competitions like the UEFA Champions League and domestic leagues such as the English Premier League, La Liga, and the Bundesliga attract enormous global followings and generate billions in revenue annually. Players like Pelé, Diego Maradona, Lionel Messi, and Cristiano Ronaldo have transcended the sport to become cultural icons recognized far beyond the soccer world.</p>",
    ],
    "Intro email": [
      "<p>Subject: Introduction — Alex Tooney, Software Engineer</p><p>Hi Jamie,</p><p>My name is Alex Tooney — I was referred to you by Priya Nair, who thought it might be worth us connecting. I'm a software engineer with a focus on developer tooling, and I've been following the work your team has been doing around internal platforms at Meridian. I'd love to find 20 minutes to swap notes and hear more about where things are headed.</p><p>Would you be open to a quick call sometime in the next couple of weeks?</p><p>Thanks,<br>Alex</p>",
    ],
  };

  function showOverlayModal(contentEl) {
    const overlay = document.createElement("div");
    overlay.className = "docs-demo-modal-overlay";
    const modal = document.createElement("div");
    modal.className = "docs-demo-modal";
    modal.appendChild(contentEl);
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
      }
    });
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    return overlay;
  }

  function loadSampleText(html) {
    if (!pageContent || !commentsGutter) return;
    // Clear comments
    commentsGutter.innerHTML = "";
    // Clear any comment highlights by replacing innerHTML
    pageContent.innerHTML = html;
    savedSelection = null;
    savedSelectionText = "";
    clearSelectionMarker();
    updateWordCount();
  }

  const aboutBtn = document.getElementById("docs-demo-about-btn");
  const sampleBtn = document.getElementById("docs-demo-sample-btn");
  const runDemoBtn = document.getElementById("docs-demo-rundemo-btn");

  if (aboutBtn) {
    aboutBtn.addEventListener("click", function () {
      const content = document.createElement("div");
      content.innerHTML = [
        '<h2 class="docs-demo-modal-title">About this demo</h2>',
        "<p>This demo includes two ideas for Gemini in Google Docs.</p>",
        "<p>The first idea is slash commands / skills. These are common in many AI powered editors and I think they would be a natural fit in Docs. The reusability would save time and bring consistency across organizations. In the demo, I have hardcoded a few commands that you can use, but Docs would allow users to define their own commands.</p>",
        "<ul>",
        "<li><strong>/improve</strong> — rewrites your text to be clearer and more professional</li>",
        "<li><strong>/expand</strong> — adds more detail and elaboration</li>",
        "<li><strong>/summarize</strong> — condenses the text into a shorter summary</li>",
        "<li><strong>/brainstorm</strong> — generates bullet-point ideas (select a topic first)</li>",
        "<li><strong>/review</strong> — adds AI comments to the document with passage-level feedback</li>",
        "<li><strong>/comment [instructions]</strong> — adds targeted comments based on your instructions, e.g. <em>/comment look for passive voice</em></li>",
        "</ul>",
        "<p>The second idea is re-using Docos as the interface for the AI to give feedback on the doc. I think Docos are one of the defining features of Docs, and I think this feedback format would make some users more likely to opt for Docs over LLM chatbots. Comments are nice because they don't interrupt the flow (in terms of both text and user focus). Gemini could periodically scan and provide feedback in comments while you are writing.</p>",
        '<button class="docs-demo-modal-close-btn" id="docs-demo-about-close">Got it</button>',
      ].join("");
      const overlay = showOverlayModal(content);
      content
        .querySelector("#docs-demo-about-close")
        .addEventListener("click", function () {
          document.body.removeChild(overlay);
        });
    });
  }

  if (sampleBtn) {
    sampleBtn.addEventListener("click", function () {
      const content = document.createElement("div");
      content.innerHTML =
        '<h2 class="docs-demo-modal-title">Choose sample text</h2><p>This will replace the current document content.</p><div class="docs-demo-sample-options" id="docs-demo-sample-options"></div>';
      const overlay = showOverlayModal(content);
      const optionsEl = content.querySelector("#docs-demo-sample-options");
      Object.keys(SAMPLE_TEXTS).forEach(function (label) {
        const btn = document.createElement("button");
        btn.className = "docs-demo-sample-option-btn";
        btn.textContent = label;
        btn.addEventListener("click", function () {
          const options = SAMPLE_TEXTS[label];
          const html = options[Math.floor(Math.random() * options.length)];
          loadSampleText(html);
          document.body.removeChild(overlay);
          showDemoTooltip('Now type / in the pill below');
          setTimeout(hideDemoTooltip, 3500);
        });
        optionsEl.appendChild(btn);
      });
    });
  }

  function showDemoTooltip(text) {
    var existing = document.getElementById('docs-demo-demo-tooltip');
    if (existing) existing.remove();
    var tip = document.createElement('div');
    tip.id = 'docs-demo-demo-tooltip';
    tip.className = 'docs-demo-demo-tooltip';
    tip.textContent = text;
    if (commandPillWrapper) {
      commandPillWrapper.style.position = 'relative';
      commandPillWrapper.appendChild(tip);
    }
    return tip;
  }

  function hideDemoTooltip() {
    var tip = document.getElementById('docs-demo-demo-tooltip');
    if (tip) tip.remove();
  }

  if (runDemoBtn) {
    runDemoBtn.addEventListener('click', function () {
      runDemoBtn.disabled = true;

      // Step 1: show tooltip then load sample text
      showDemoTooltip('Writing some text…');
      setTimeout(function () {
        loadSampleText(SAMPLE_TEXTS['Fake student writing'][0]);
      }, 400);

      // Step 2: focus pill, type /, show autocomplete
      setTimeout(function () {
        if (!commandInput) return;
        commandInput.focus();
        commandInput.value = '/';
        showAutocomplete('/');
        showDemoTooltip('Typing a slash command…');
      }, 1900);

      // Step 3: highlight /review in autocomplete
      setTimeout(function () {
        autocompleteSelectedIndex = autocompleteFilteredCommands.indexOf('/review');
        if (autocompleteSelectedIndex < 0) autocompleteSelectedIndex = 0;
        updateAutocompleteSelection();
        showDemoTooltip('Selecting /review…');
      }, 5200);

      // Step 4: select it — fills the input
      setTimeout(function () {
        selectAutocompleteItem('/review');
        showDemoTooltip('Running /review…');
      }, 7400);

      // Step 5: submit
      setTimeout(function () {
        hideDemoTooltip();
        hideAutocomplete();
        handleCommentsCommand('/review', '');
        if (commandInput) commandInput.value = '/review';
        runDemoBtn.disabled = false;
      }, 9200);
    });
  }

  updateWordCount();
})();

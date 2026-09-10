(function () {
  const cfg = window.KIDS_AI || {};
  const listEl = document.getElementById("kidsAiConversationList");
  const messagesEl = document.getElementById("kidsAiMessages");
  const emptyEl = document.getElementById("kidsAiEmpty");
  const inputEl = document.getElementById("kidsAiInput");
  const sendEl = document.getElementById("kidsAiSend");
  const composerEl = document.getElementById("kidsAiComposer");
  const bannerEl = document.getElementById("kidsAiBanner");
  const newBtn = document.getElementById("kidsAiNewConversation");

  let currentId = null;
  let sending = false;
  let waitingPass2 = false;
  let pollTimer = null;

  function headers() {
    return {
      "Content-Type": "application/json",
      "X-CSRFToken": cfg.csrfToken || "",
    };
  }

  function urlWithId(template, id) {
    return (template || "").replace("__ID__", String(id));
  }

  function showBanner(text, isError) {
    if (!bannerEl) return;
    if (!text) {
      bannerEl.hidden = true;
      bannerEl.textContent = "";
      return;
    }
    bannerEl.hidden = false;
    bannerEl.textContent = text;
    bannerEl.classList.toggle("kids-ai-chat-banner-error", Boolean(isError));
  }

  function setComposerEnabled(enabled) {
    if (!inputEl || !sendEl) return;
    const allowed = Boolean(cfg.canSend) && enabled && !sending && !waitingPass2;
    inputEl.disabled = !allowed;
    sendEl.disabled = !allowed || !inputEl.value.trim();
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function formatDate(iso) {
    if (!iso) return "";
    const date = new Date(iso);
    return date.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  }

  function addMessage(payload) {
    if (emptyEl) emptyEl.hidden = true;
    const row = document.createElement("div");
    const isChild = payload.role === "child";
    row.className =
      "kids-ai-chat-bubble " +
      (isChild ? "kids-ai-chat-bubble-child" : "kids-ai-chat-bubble-assistant");
    if (!isChild && payload.body_html) {
      row.innerHTML = payload.body_html;
    } else {
      row.textContent = payload.body || "";
    }
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function clearMessages(showEmpty) {
    messagesEl.querySelectorAll(".kids-ai-chat-bubble").forEach(function (el) {
      el.remove();
    });
    if (emptyEl) emptyEl.hidden = !showEmpty;
  }

  function renderConversationList(conversations) {
    listEl.innerHTML = "";
    if (!conversations.length) {
      const p = document.createElement("p");
      p.className = "kids-ai-muted";
      p.textContent = "No conversations yet.";
      listEl.appendChild(p);
      return;
    }
    conversations.forEach(function (conv) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "kids-ai-chat-item";
      if (String(conv.id) === String(currentId)) {
        btn.classList.add("kids-ai-chat-item-active");
      }
      btn.innerHTML =
        '<span class="kids-ai-chat-item-title"></span>' +
        '<span class="kids-ai-chat-item-date"></span>';
      btn.querySelector(".kids-ai-chat-item-title").textContent =
        conv.title || "New conversation";
      btn.querySelector(".kids-ai-chat-item-date").textContent = formatDate(
        conv.modified_at
      );
      btn.addEventListener("click", function () {
        loadConversation(conv.id);
      });
      listEl.appendChild(btn);
    });
  }

  function loadConversations() {
    return fetch(cfg.urls.conversations, { headers: headers() })
      .then(function (res) {
        if (res.status === 401) {
          window.location.href = "/kids-ai/login";
          return [];
        }
        return res.json();
      })
      .then(function (conversations) {
        if (Array.isArray(conversations)) {
          renderConversationList(conversations);
        }
      })
      .catch(function () {
        listEl.innerHTML = '<p class="kids-ai-muted">Could not load conversations.</p>';
      });
  }

  function handleLock(data) {
    stopPoll();
    waitingPass2 = false;
    sending = false;
    showBanner(data.warning || "This conversation had to stop.", true);
    setTimeout(function () {
      currentId = null;
      clearMessages(true);
      setComposerEnabled(true);
      loadConversations();
      if (data.paused) {
        cfg.canSend = false;
        cfg.paused = true;
        if (inputEl) {
          inputEl.disabled = true;
          inputEl.placeholder = "Chatting is paused";
        }
        if (newBtn) newBtn.disabled = true;
        setComposerEnabled(false);
      }
    }, 1200);
  }

  function startPass2(conversationId) {
    waitingPass2 = true;
    setComposerEnabled(false);
    showBanner("Checking this reply…");

    fetch(urlWithId(cfg.urls.pass2, conversationId), {
      method: "POST",
      headers: headers(),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        waitingPass2 = false;
        if (result.data.status === "locked") {
          handleLock(result.data);
          return;
        }
        showBanner("");
        setComposerEnabled(true);
        loadConversations();
      })
      .catch(function () {
        waitingPass2 = false;
        showBanner("");
        setComposerEnabled(true);
      });

    stopPoll();
    pollTimer = setInterval(function () {
      fetch(urlWithId(cfg.urls.status, conversationId), { headers: headers() })
        .then(function (res) {
          return res.json();
        })
        .then(function (data) {
          if (data.status === "locked") {
            handleLock(data);
            return;
          }
          if (!data.pass2_pending) {
            stopPoll();
            waitingPass2 = false;
            showBanner("");
            setComposerEnabled(true);
          }
        })
        .catch(function () {});
    }, 1500);
  }

  function loadConversation(id) {
    stopPoll();
    waitingPass2 = false;
    currentId = id;
    showBanner("");
    fetch(urlWithId(cfg.urls.conversationMessages, id), { headers: headers() })
      .then(function (res) {
        if (!res.ok) throw new Error("missing");
        return res.json();
      })
      .then(function (data) {
        clearMessages(false);
        (data.messages || []).forEach(addMessage);
        if (!(data.messages || []).length && emptyEl) emptyEl.hidden = false;
        document.querySelectorAll(".kids-ai-chat-item").forEach(function (el) {
          el.classList.toggle(
            "kids-ai-chat-item-active",
            el.querySelector(".kids-ai-chat-item-title") &&
              el.textContent.indexOf(data.title || "") !== -1
          );
        });
        loadConversations();
        if (data.pass2_pending) {
          startPass2(id);
        } else {
          setComposerEnabled(true);
        }
      })
      .catch(function () {
        showBanner("Could not open that conversation.", true);
        currentId = null;
        clearMessages(true);
      });
  }

  function sendMessage(event) {
    if (event) event.preventDefault();
    if (!cfg.canSend || sending || waitingPass2) return;
    const text = (inputEl.value || "").trim();
    if (!text) return;

    sending = true;
    setComposerEnabled(false);
    showBanner("Sending…");

    fetch(cfg.urls.send, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        message: text,
        conversation_id: currentId,
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          return { status: res.status, data: data };
        });
      })
      .then(function (result) {
        sending = false;
        const data = result.data || {};
        if (data.status === "locked") {
          handleLock(data);
          return;
        }
        if (data.status !== "ok") {
          showBanner(
            data.warning || data.error || "Could not send. Please try again.",
            true
          );
          setComposerEnabled(true);
          return;
        }
        currentId = data.conversation_id;
        inputEl.value = "";
        if (emptyEl) emptyEl.hidden = true;
        if (data.child_message) {
          addMessage(data.child_message);
        }
        if (data.assistant_message) {
          addMessage(data.assistant_message);
        }
        loadConversations();
        if (data.pass2_pending && currentId) {
          startPass2(currentId);
        } else {
          setComposerEnabled(true);
        }
      })
      .catch(function () {
        sending = false;
        showBanner("Could not send. Please try again.", true);
        setComposerEnabled(true);
      });
  }

  if (composerEl) {
    composerEl.addEventListener("submit", sendMessage);
  }
  if (inputEl) {
    inputEl.addEventListener("input", function () {
      setComposerEnabled(true);
    });
    inputEl.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
      }
    });
  }
  if (newBtn) {
    newBtn.addEventListener("click", function () {
      stopPoll();
      waitingPass2 = false;
      currentId = null;
      showBanner("");
      clearMessages(true);
      setComposerEnabled(true);
      document.querySelectorAll(".kids-ai-chat-item-active").forEach(function (el) {
        el.classList.remove("kids-ai-chat-item-active");
      });
      inputEl && inputEl.focus();
    });
  }

  setComposerEnabled(true);
  loadConversations();
})();

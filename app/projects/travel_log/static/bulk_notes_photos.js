/**
 * Travel Log bulk notes + photos editor.
 * - Notes autosave per entry (debounced)
 * - Save all fallback button
 * - Photo upload per entry via existing presign/confirm APIs
 */
(function () {
  const root = document.getElementById("tlog-bulk-root");
  if (!root) return;

  const csrfToken = root.getAttribute("data-csrf-token") ||
    document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") ||
    "";
  const globalStatusEl = document.getElementById("tlog-bulk-global-status");
  const saveAllBtn = document.getElementById("tlog-bulk-save-all-btn");

  const MAX_EDGE = 1200;
  const JPEG_QUALITY = 0.8;
  const DEBOUNCE_MS = 800;

  const stateByEntryId = new Map();

  function ensureEntryState(entryId) {
    if (!stateByEntryId.has(entryId)) {
      stateByEntryId.set(entryId, {
        dirty: false,
        saving: false,
        timer: null,
        saveRevision: 0,
        uploadCount: 0,
        error: null,
      });
    }
    return stateByEntryId.get(entryId);
  }

  function statusElFor(entryId) {
    return document.getElementById(`tlog-bulk-status-${entryId}`);
  }

  function setEntryStatus(entryId, message, isError) {
    const el = statusElFor(entryId);
    if (!el) return;
    el.textContent = message;
    el.classList.toggle("tlog-bulk-item-status-error", !!isError);
  }

  function refreshGlobalStatus() {
    if (!globalStatusEl) return;
    let dirty = 0;
    let saving = 0;
    let errors = 0;
    let uploading = 0;
    stateByEntryId.forEach((s) => {
      if (s.dirty) dirty += 1;
      if (s.saving) saving += 1;
      if (s.error) errors += 1;
      if (s.uploadCount > 0) uploading += s.uploadCount;
    });

    if (errors > 0) {
      globalStatusEl.textContent = `${errors} place${errors === 1 ? "" : "s"} need attention.`;
      globalStatusEl.classList.add("tlog-bulk-global-status-error");
      return;
    }
    globalStatusEl.classList.remove("tlog-bulk-global-status-error");
    if (uploading > 0) {
      globalStatusEl.textContent = `Uploading ${uploading} photo${uploading === 1 ? "" : "s"}...`;
      return;
    }
    if (saving > 0) {
      globalStatusEl.textContent = `Saving ${saving} place${saving === 1 ? "" : "s"}...`;
      return;
    }
    if (dirty > 0) {
      globalStatusEl.textContent = `${dirty} unsaved change${dirty === 1 ? "" : "s"}.`;
      return;
    }
    globalStatusEl.textContent = "All changes saved.";
  }

  async function saveNotes(entryId, explicitText) {
    const state = ensureEntryState(entryId);
    const input = document.querySelector(`.tlog-bulk-notes-input[data-entry-id="${entryId}"]`);
    if (!input) return;
    const notes = explicitText != null ? explicitText : input.value;

    state.saveRevision += 1;
    const revision = state.saveRevision;
    state.saving = true;
    state.error = null;
    setEntryStatus(entryId, "Saving...", false);
    refreshGlobalStatus();

    try {
      const res = await fetch(`/travel-log/api/entries/${entryId}/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ notes }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Save failed.");
      }
      if (state.saveRevision === revision) {
        state.dirty = false;
        state.error = null;
        setEntryStatus(entryId, "Saved", false);
      }
    } catch (err) {
      state.error = err.message || "Save failed.";
      setEntryStatus(entryId, "Error saving notes", true);
    } finally {
      state.saving = false;
      refreshGlobalStatus();
    }
  }

  function queueAutosave(entryId) {
    const state = ensureEntryState(entryId);
    state.dirty = true;
    state.error = null;
    setEntryStatus(entryId, "Unsaved changes", false);
    if (state.timer) clearTimeout(state.timer);
    state.timer = setTimeout(() => {
      state.timer = null;
      saveNotes(entryId);
    }, DEBOUNCE_MS);
    refreshGlobalStatus();
  }

  function compressImage(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        let w = img.width;
        let h = img.height;
        if (w > MAX_EDGE || h > MAX_EDGE) {
          if (w > h) {
            h = (h * MAX_EDGE) / w;
            w = MAX_EDGE;
          } else {
            w = (w * MAX_EDGE) / h;
            h = MAX_EDGE;
          }
        }
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, w, h);
        canvas.toBlob((blob) => resolve(blob || new Blob()), "image/jpeg", JPEG_QUALITY);
      };
      img.onerror = () => reject(new Error("Failed to load image"));
      img.src = URL.createObjectURL(file);
    });
  }

  function appendPhoto(entryId, viewUrl) {
    const grid = document.getElementById(`tlog-bulk-photos-grid-${entryId}`);
    if (!grid || !viewUrl) return;
    const item = document.createElement("div");
    item.className = "tlog-photo-item";
    item.innerHTML = `<img src="${viewUrl.replace(/"/g, "&quot;")}" alt="Photo" class="tlog-photo-img" loading="lazy">`;
    grid.appendChild(item);
  }

  async function uploadSinglePhoto(entryId, file) {
    const state = ensureEntryState(entryId);
    state.uploadCount += 1;
    state.error = null;
    setEntryStatus(entryId, "Uploading photo...", false);
    refreshGlobalStatus();
    try {
      const blob = await compressImage(file);

      const presignRes = await fetch("/travel-log/api/photos/presign", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({ entry_id: entryId }),
      });
      const presignData = await presignRes.json();
      if (!presignRes.ok || !presignData.upload_url || !presignData.key) {
        throw new Error(presignData.error || "Failed to get upload URL");
      }

      const putRes = await fetch(presignData.upload_url, {
        method: "PUT",
        body: blob,
        headers: { "Content-Type": "image/jpeg" },
      });
      if (!putRes.ok) {
        throw new Error(`Upload failed (${putRes.status})`);
      }

      const confirmRes = await fetch("/travel-log/api/photos/confirm", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          entry_id: entryId,
          key: presignData.key,
        }),
      });
      const confirmData = await confirmRes.json();
      if (!confirmRes.ok || !confirmData.success) {
        throw new Error(confirmData.error || "Failed to save photo");
      }
      appendPhoto(entryId, confirmData.view_url || "");
      setEntryStatus(entryId, "Saved", false);
    } catch (err) {
      state.error = err.message || "Photo upload failed.";
      setEntryStatus(entryId, "Error uploading photo", true);
    } finally {
      state.uploadCount = Math.max(0, state.uploadCount - 1);
      refreshGlobalStatus();
    }
  }

  async function saveAllNow() {
    const tasks = [];
    document.querySelectorAll(".tlog-bulk-notes-input").forEach((input) => {
      const entryId = Number(input.getAttribute("data-entry-id"));
      if (!entryId) return;
      const state = ensureEntryState(entryId);
      if (state.timer) {
        clearTimeout(state.timer);
        state.timer = null;
      }
      tasks.push(saveNotes(entryId, input.value));
    });
    await Promise.all(tasks);
  }

  document.querySelectorAll(".tlog-bulk-notes-input").forEach((input) => {
    const entryId = Number(input.getAttribute("data-entry-id"));
    if (!entryId) return;
    ensureEntryState(entryId);
    input.addEventListener("input", () => queueAutosave(entryId));
  });

  document.querySelectorAll(".tlog-bulk-photo-input").forEach((input) => {
    input.addEventListener("change", async function () {
      const entryId = Number(this.getAttribute("data-entry-id"));
      if (!entryId) return;
      const files = Array.from(this.files || []);
      this.value = "";
      for (const file of files) {
        if (!file.type.startsWith("image/")) continue;
        await uploadSinglePhoto(entryId, file);
      }
    });
  });

  if (saveAllBtn) {
    saveAllBtn.addEventListener("click", async function () {
      this.disabled = true;
      await saveAllNow();
      this.disabled = false;
    });
  }

  window.addEventListener("beforeunload", function (e) {
    const hasPending = Array.from(stateByEntryId.values()).some((s) => s.dirty || s.saving || s.uploadCount > 0);
    if (!hasPending) return;
    e.preventDefault();
    e.returnValue = "";
  });

  refreshGlobalStatus();
})();

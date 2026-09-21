(function () {
  var dataNode = document.getElementById("scm-field-stretches");
  var dialog = document.getElementById("scm-field-dialog");
  var title = document.getElementById("scm-field-dialog-title");
  var statusNode = document.getElementById("scm-field-dialog-status");
  var pitch = document.getElementById("scm-field-stretch-pitch");
  var resetBtn = document.getElementById("scm-field-dialog-reset");
  var saveBtn = document.getElementById("scm-field-dialog-save");
  var closeBtn = document.getElementById("scm-field-dialog-close");
  if (!dataNode || !dialog || !pitch) {
    return;
  }

  var stretches = {};
  try {
    stretches = JSON.parse(dataNode.textContent || "{}") || {};
  } catch (err) {
    stretches = {};
  }

  var working = null;
  var selectedKey = null;
  var saving = false;

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function showStatus(text, isError) {
    if (!statusNode) {
      return;
    }
    if (!text) {
      statusNode.hidden = true;
      statusNode.textContent = "";
      statusNode.classList.remove("scm-roster-status-error");
      return;
    }
    statusNode.hidden = false;
    statusNode.textContent = text;
    statusNode.classList.toggle("scm-roster-status-error", !!isError);
  }

  function isDirty() {
    if (!working) {
      return false;
    }
    return (
      JSON.stringify(working.assignments) !==
      JSON.stringify(working.original.assignments)
    );
  }

  function slotByKey(slotKey) {
    var found = null;
    (working.bands || []).forEach(function (band) {
      band.slots.forEach(function (slot) {
        if (slot.key === slotKey) {
          found = slot;
        }
      });
    });
    return found;
  }

  function renderPitch() {
    pitch.innerHTML = "";
    if (!working) {
      return;
    }
    (working.bands || []).forEach(function (band) {
      var bandEl = document.createElement("div");
      bandEl.className = "scm-pitch-band scm-pitch-band-" + band.group;
      var label = document.createElement("span");
      label.className = "scm-pitch-band-label";
      label.textContent = band.label;
      var slots = document.createElement("div");
      slots.className = "scm-pitch-slots";
      band.slots.forEach(function (slot) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "scm-pitch-slot scm-field-slot";
        if (slot.player_id) {
          btn.classList.add("scm-slot-filled");
        }
        if (selectedKey === slot.key) {
          btn.classList.add("scm-is-selected");
        }
        btn.setAttribute("data-slot-key", slot.key);
        if (slot.player_full_label) {
          btn.title = slot.player_full_label;
        }
        var pos = document.createElement("span");
        pos.className = "scm-slot-pos";
        pos.textContent = slot.name;
        var who = document.createElement("span");
        who.className = "scm-slot-who";
        who.textContent = slot.player_label || "—";
        btn.appendChild(pos);
        btn.appendChild(who);
        slots.appendChild(btn);
      });
      bandEl.appendChild(label);
      bandEl.appendChild(slots);
      pitch.appendChild(bandEl);
    });
    var dirty = isDirty();
    if (resetBtn) {
      resetBtn.disabled = !dirty || saving;
    }
    if (saveBtn) {
      saveBtn.disabled = !dirty || saving;
    }
  }

  function swapSlots(aKey, bKey) {
    var a = slotByKey(aKey);
    var b = slotByKey(bKey);
    if (!a || !b || !a.player_id || !b.player_id || aKey === bKey) {
      return;
    }
    var aPlayer = a.player_id;
    var aLabel = a.player_label;
    var aFull = a.player_full_label;
    a.player_id = b.player_id;
    a.player_label = b.player_label;
    a.player_full_label = b.player_full_label;
    b.player_id = aPlayer;
    b.player_label = aLabel;
    b.player_full_label = aFull;
    working.assignments[aKey] = a.player_id;
    working.assignments[bKey] = b.player_id;
  }

  function onSlotTap(slotKey) {
    if (saving) {
      return;
    }
    var slot = slotByKey(slotKey);
    if (!slot || !slot.player_id) {
      selectedKey = null;
      renderPitch();
      return;
    }
    if (selectedKey === slotKey) {
      selectedKey = null;
      renderPitch();
      return;
    }
    if (selectedKey) {
      swapSlots(selectedKey, slotKey);
      selectedKey = null;
      renderPitch();
      return;
    }
    selectedKey = slotKey;
    renderPitch();
  }

  function openStretch(eventId) {
    var source = stretches[String(eventId)] || stretches[eventId];
    if (!source) {
      return;
    }
    working = clone(source);
    working.original = clone(source);
    selectedKey = null;
    showStatus("");
    if (title) {
      title.textContent =
        "Period " +
        source.period +
        " · " +
        source.start +
        "–" +
        source.end;
    }
    renderPitch();
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
  }

  function closeDialog() {
    if (typeof dialog.close === "function") {
      dialog.close();
    } else {
      dialog.removeAttribute("open");
    }
  }

  function saveStretch() {
    if (!working || !working.saveUrl || saving || !isDirty()) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    renderPitch();
    fetch(working.saveUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify({ assignments: working.assignments }),
    })
      .then(function (response) {
        return response.text().then(function (text) {
          var data;
          try {
            data = JSON.parse(text);
          } catch (err) {
            data = { ok: false, error: "Could not save. Try again." };
          }
          if (!response.ok) {
            data.ok = false;
            data.error = data.error || "Could not save. Try again.";
          }
          return data;
        });
      })
      .then(function (data) {
        saving = false;
        if (!data.ok) {
          showStatus(data.error || "Could not save. Try again.", true);
          renderPitch();
          return;
        }
        window.location.reload();
      })
      .catch(function () {
        saving = false;
        showStatus("Could not save. Check your connection.", true);
        renderPitch();
      });
  }

  document.addEventListener("click", function (event) {
    var btn = event.target.closest(".scm-stretch-open");
    if (!btn) {
      return;
    }
    openStretch(btn.getAttribute("data-stretch-id"));
  });

  pitch.addEventListener("click", function (event) {
    var btn = event.target.closest(".scm-field-slot");
    if (!btn || !pitch.contains(btn)) {
      return;
    }
    onSlotTap(btn.getAttribute("data-slot-key"));
  });

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      if (!working || saving) {
        return;
      }
      working = clone(working.original);
      working.original = clone(working);
      selectedKey = null;
      showStatus("");
      renderPitch();
    });
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", saveStretch);
  }

  if (closeBtn) {
    closeBtn.addEventListener("click", closeDialog);
  }

  dialog.addEventListener("click", function (event) {
    if (event.target === dialog) {
      closeDialog();
    }
  });
})();

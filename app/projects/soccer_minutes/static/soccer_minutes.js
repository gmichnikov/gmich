(function () {
  var editor = document.getElementById("scm-formation-editor");
  if (!editor) {
    return;
  }

  var GROUP_LABELS = {
    fwd: "Forwards",
    mid: "Midfield",
    def: "Defense",
    gk: "Goalkeeper",
  };
  var PLACEHOLDER = { def: "DEF", mid: "MID", fwd: "FWD" };
  var BANDS = ["fwd", "mid", "def", "gk"];
  var MAX_LINE = 8;

  function clampCount(value) {
    var n = parseInt(value, 10);
    if (isNaN(n) || n < 0) {
      return 0;
    }
    if (n > MAX_LINE) {
      return MAX_LINE;
    }
    return n;
  }

  function slotKey(group, index) {
    return group === "gk" ? "gk" : group + "_" + index;
  }

  function placeholderName(group, index) {
    if (group === "gk") {
      return "GK";
    }
    return PLACEHOLDER[group] + " " + (index + 1);
  }

  function namesContainer() {
    return document.getElementById("scm-slot-names");
  }

  function countFor(group) {
    if (group === "gk") {
      return 1;
    }
    var input = editor.querySelector('.scm-count-input[data-group="' + group + '"]');
    return input ? clampCount(input.value) : 0;
  }

  function snapshotNames() {
    var map = {};
    editor.querySelectorAll(".scm-slot-name-input").forEach(function (input) {
      var key = input.getAttribute("name").replace("slot_name_", "");
      map[key] = input.value;
    });
    return map;
  }

  function currentName(saved, key, group, index) {
    if (saved[key] && saved[key].trim()) {
      return saved[key].trim();
    }
    return placeholderName(group, index);
  }

  function buildNameRow(saved, group, index) {
    var key = slotKey(group, index);
    var labelText =
      group === "gk" ? "Name" : "Left to right " + (index + 1);
    var wrap = document.createElement("div");
    wrap.className = "scm-form-group scm-slot-name-row";
    wrap.setAttribute("data-slot-key", key);
    wrap.innerHTML =
      '<label class="scm-label" for="scm-slot-' +
      key +
      '">' +
      labelText +
      "</label>" +
      '<input type="text" id="scm-slot-' +
      key +
      '" name="slot_name_' +
      key +
      '" class="scm-input scm-slot-name-input" maxlength="20" required>';
    wrap.querySelector("input").value = currentName(saved, key, group, index);
    wrap.querySelector("input").addEventListener("input", renderPitch);
    return wrap;
  }

  function rebuildNames() {
    var root = namesContainer();
    if (!root) {
      return;
    }
    var saved = snapshotNames();
    BANDS.forEach(function (group) {
      var section = root.querySelector('.scm-slot-group[data-group="' + group + '"]');
      if (!section) {
        return;
      }
      var count = countFor(group);
      section.innerHTML = '<h3 class="scm-slot-group-title">' + GROUP_LABELS[group] + "</h3>";
      if (count === 0) {
        var empty = document.createElement("p");
        empty.className = "scm-muted scm-slot-none";
        empty.textContent = "No slots in this line.";
        section.appendChild(empty);
        return;
      }
      for (var i = 0; i < count; i += 1) {
        section.appendChild(buildNameRow(saved, group, i));
      }
    });
    renderPitch();
  }

  function renderPitch() {
    var pitch = editor.querySelector(".scm-pitch");
    var sizeEl = editor.querySelector(".scm-field-size-n");
    if (!pitch) {
      return;
    }
    var total = 0;
    BANDS.forEach(function (group) {
      var band = pitch.querySelector('.scm-pitch-band[data-group="' + group + '"]');
      if (!band) {
        return;
      }
      var slotsWrap = band.querySelector(".scm-pitch-slots");
      var count = countFor(group);
      total += count;
      slotsWrap.innerHTML = "";
      if (count === 0) {
        var none = document.createElement("span");
        none.className = "scm-pitch-empty";
        none.textContent = "None";
        slotsWrap.appendChild(none);
        return;
      }
      for (var i = 0; i < count; i += 1) {
        var key = slotKey(group, i);
        var nameInput = editor.querySelector('[name="slot_name_' + key + '"]');
        var slot = document.createElement("span");
        slot.className = "scm-pitch-slot";
        slot.setAttribute("data-slot-key", key);
        slot.textContent = nameInput ? nameInput.value.trim() || placeholderName(group, i) : placeholderName(group, i);
        slotsWrap.appendChild(slot);
      }
    });
    if (sizeEl) {
      sizeEl.textContent = String(total);
    }
  }

  editor.querySelectorAll(".scm-count-input").forEach(function (input) {
    input.addEventListener("change", rebuildNames);
    input.addEventListener("input", rebuildNames);
  });
  editor.querySelectorAll(".scm-slot-name-input").forEach(function (input) {
    input.addEventListener("input", renderPitch);
  });
})();

(function () {
  var roster = document.getElementById("scm-roster");
  if (!roster) {
    return;
  }

  var list = document.getElementById("scm-roster-list");
  var status = document.getElementById("scm-roster-status");
  var addForm = document.getElementById("scm-roster-add");

  function showStatus(text, isError) {
    if (!status) {
      return;
    }
    if (!text) {
      status.hidden = true;
      status.textContent = "";
      return;
    }
    status.hidden = false;
    status.textContent = text;
    status.classList.toggle("scm-roster-status-error", !!isError);
  }

  function replaceList(html) {
    if (list) {
      list.innerHTML = html;
    }
  }

  function postForm(form) {
    return fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    }).then(function (response) {
      return response.json().then(function (data) {
        data.status = response.status;
        return data;
      });
    });
  }

  roster.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.classList.contains("scm-roster-ajax-form")) {
      return;
    }
    event.preventDefault();
    postForm(form)
      .then(function (data) {
        if (data.html) {
          replaceList(data.html);
        }
        if (!data.ok) {
          showStatus(data.error || "Could not update roster.", true);
          return;
        }
        if (form.id === "scm-roster-add") {
          form.reset();
          var first = form.querySelector('[name="first_name"]');
          if (first) {
            first.focus();
          }
        }
        showStatus(data.message || "");
      })
      .catch(function () {
        showStatus("Could not update roster. Check your connection.", true);
      });
  });
})();

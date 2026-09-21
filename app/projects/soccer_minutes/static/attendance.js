(function () {
  var stateNode = document.getElementById("scm-attendance-state");
  var attendanceRoot = document.getElementById("scm-attendance");
  var statusNode = document.getElementById("scm-attendance-status");
  var csrfNode = document.getElementById("scm-csrf");
  if (!stateNode || !attendanceRoot) {
    return;
  }

  var state = JSON.parse(stateNode.textContent);
  var saving = false;

  function csrfToken() {
    if (csrfNode && csrfNode.value) {
      return csrfNode.value;
    }
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
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

  function render() {
    attendanceRoot.innerHTML = "";
    (state.attendance || []).forEach(function (person) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "scm-attendance-btn";
      if (!person.is_present) {
        btn.classList.add("scm-is-absent");
      }
      btn.setAttribute("data-player-id", String(person.id));
      btn.setAttribute("aria-pressed", person.is_present ? "false" : "true");
      if (person.jersey_number) {
        var jersey = document.createElement("span");
        jersey.className = "scm-jersey";
        jersey.textContent = person.jersey_number;
        btn.appendChild(jersey);
      }
      var name = document.createElement("span");
      name.className = "scm-attendance-name";
      name.textContent = person.full_name;
      btn.appendChild(name);
      var flagEl = document.createElement("span");
      flagEl.className = "scm-attendance-flag";
      flagEl.textContent = person.is_present ? "Here" : "Out";
      btn.appendChild(flagEl);
      li.appendChild(btn);
      attendanceRoot.appendChild(li);
    });
  }

  function onTap(playerId) {
    if (saving || !state.attendanceUrl) {
      return;
    }
    var person = null;
    (state.attendance || []).forEach(function (item) {
      if (item.id === playerId) {
        person = item;
      }
    });
    if (!person) {
      return;
    }
    saving = true;
    showStatus("Saving…");
    fetch(state.attendanceUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfToken(),
      },
      body: JSON.stringify({
        player_id: playerId,
        present: !person.is_present,
      }),
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
          showStatus(data.error || "Could not update attendance.", true);
          return;
        }
        if (data.attendance) {
          state.attendance = data.attendance;
        }
        render();
        showStatus("");
      })
      .catch(function () {
        saving = false;
        showStatus("Could not update attendance. Check your connection.", true);
      });
  }

  attendanceRoot.addEventListener("click", function (event) {
    var btn = event.target.closest(".scm-attendance-btn");
    if (!btn || !attendanceRoot.contains(btn)) {
      return;
    }
    onTap(parseInt(btn.getAttribute("data-player-id"), 10));
  });
})();

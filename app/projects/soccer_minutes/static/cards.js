(function () {
  var STORAGE_KEY = "scm-card-collapsed";
  var cards = document.querySelectorAll(".scm-card");
  if (!cards.length) {
    return;
  }

  function loadState() {
    try {
      var raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      return raw && typeof raw === "object" ? raw : {};
    } catch (err) {
      return {};
    }
  }

  function saveState(state) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (err) {
      /* ignore */
    }
  }

  function titleText(header) {
    var clone = header.cloneNode(true);
    clone.querySelectorAll("a, button, input, select, textarea").forEach(function (el) {
      el.remove();
    });
    return (clone.textContent || "").replace(/\s+/g, " ").trim();
  }

  function cardKey(card, header) {
    var path = window.location.pathname;
    if (card.id) {
      return path + "#" + card.id;
    }
    return path + "#" + titleText(header);
  }

  function setCollapsed(card, header, body, fold, collapsed) {
    card.classList.toggle("scm-is-collapsed", collapsed);
    body.hidden = collapsed;
    fold.setAttribute("aria-expanded", collapsed ? "false" : "true");
    var label = titleText(header) || "Section";
    fold.setAttribute(
      "aria-label",
      (collapsed ? "Expand " : "Collapse ") + label
    );
  }

  var state = loadState();
  var hash = window.location.hash || "";

  cards.forEach(function (card, index) {
    var header = card.querySelector(".scm-card-header");
    var body = card.querySelector(".scm-card-body");
    if (!header || !body) {
      return;
    }

    if (!body.id) {
      body.id = (card.id || "scm-card-" + index) + "-body";
    }

    var fold = document.createElement("button");
    fold.type = "button";
    fold.className = "scm-card-fold";
    fold.setAttribute("aria-controls", body.id);
    fold.innerHTML = '<span class="scm-card-chevron" aria-hidden="true"></span>';
    header.appendChild(fold);

    var key = cardKey(card, header);
    var collapsed = !!state[key];
    if (hash && card.id && hash === "#" + card.id) {
      collapsed = false;
    }
    setCollapsed(card, header, body, fold, collapsed);

    function toggle() {
      var next = !card.classList.contains("scm-is-collapsed");
      setCollapsed(card, header, body, fold, next);
      var stored = loadState();
      if (next) {
        stored[key] = true;
      } else {
        delete stored[key];
      }
      saveState(stored);
    }

    fold.addEventListener("click", function (event) {
      event.stopPropagation();
      toggle();
    });

    header.addEventListener("click", function (event) {
      if (event.target.closest("a, button, input, select, textarea, label")) {
        return;
      }
      toggle();
    });
  });
})();

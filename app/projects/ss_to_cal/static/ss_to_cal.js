(function () {
  "use strict";

  var FIELD_MAP = {
    title: "sstc-title",
    date: "sstc-date",
    startTime: "sstc-start-time",
    endTime: "sstc-end-time",
    location: "sstc-location",
    description: "sstc-description",
  };

  var REQUIRED_FIELDS = ["title", "date", "startTime", "endTime"];

  var shareState = {
    confidence: null,
  };

  function isStandalone() {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true
    );
  }

  function initStandaloneUi() {
    var installPanel = document.getElementById("sstc-install-panel");
    var readyPanel = document.getElementById("sstc-ready-panel");
    if (!installPanel || !readyPanel) {
      return;
    }

    if (isStandalone()) {
      installPanel.hidden = true;
      readyPanel.hidden = false;
    } else {
      installPanel.hidden = false;
      readyPanel.hidden = true;
    }
  }

  function setSwStatus(message, isError) {
    var el = document.getElementById("sstc-sw-status");
    if (el) {
      el.textContent = message;
      el.classList.toggle("sstc-sw-status-error", !!isError);
    }
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator)) {
      setSwStatus("Service workers not supported in this browser.", true);
      return;
    }

    if (!window.isSecureContext) {
      setSwStatus("Service worker requires HTTPS (or localhost).", true);
      return;
    }

    navigator.serviceWorker
      .register("/ss-to-cal/sw.js", { scope: "/ss-to-cal/" })
      .then(function (registration) {
        console.log("SS to Cal service worker registered:", registration.scope);
        setSwStatus("Service worker registered (" + registration.scope + ").");
      })
      .catch(function (err) {
        console.error("SS to Cal service worker registration failed:", err);
        setSwStatus("Service worker failed: " + err.message, true);
      });
  }

  /** Device timezone — used when building Google Calendar URLs (Phase 5). */
  function deviceTimezone() {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch (e) {
      return "";
    }
  }

  function fieldValue(key) {
    var el = document.getElementById(FIELD_MAP[key]);
    if (!el) {
      return "";
    }
    return (el.value || "").trim();
  }

  function setFieldTag(key, text) {
    var tag = document.getElementById("sstc-tag-" + key);
    var wrapper = document.getElementById("sstc-field-" + key);
    if (!tag || !wrapper) {
      return;
    }

    if (text) {
      tag.textContent = text;
      tag.hidden = false;
      wrapper.classList.add("sstc-field-amber");
    } else {
      tag.textContent = "";
      tag.hidden = true;
      wrapper.classList.remove("sstc-field-amber");
    }
  }

  function updateFormUi() {
    var lowBanner = document.getElementById("sstc-low-confidence-banner");
    if (lowBanner) {
      lowBanner.hidden = shareState.confidence !== "low";
    }

    REQUIRED_FIELDS.forEach(function (key) {
      setFieldTag(key, fieldValue(key) ? null : "Required");
    });

    var calendarBtn = document.getElementById("sstc-calendar-btn");
    if (calendarBtn) {
      var ready = REQUIRED_FIELDS.every(function (key) {
        return fieldValue(key);
      });
      calendarBtn.disabled = !ready;
    }
  }

  function initShareForm() {
    var dataEl = document.getElementById("sstc-extraction-data");
    if (!dataEl) {
      return;
    }

    var extraction = {};
    try {
      extraction = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      console.warn("SS to Cal: invalid extraction JSON", err);
      return;
    }

    shareState.confidence = extraction.confidence || null;

    console.log("SS to Cal parsed extraction:", extraction);
    console.log("SS to Cal device timezone:", deviceTimezone());

    var fillReport = [];

    Object.keys(FIELD_MAP).forEach(function (key) {
      var el = document.getElementById(FIELD_MAP[key]);
      var parsedValue = extraction[key];
      var report = {
        field: key,
        parsed: parsedValue == null ? null : String(parsedValue),
        applied: null,
        note: "",
      };

      if (!el) {
        report.note = "input missing";
        fillReport.push(report);
        return;
      }

      if (parsedValue == null || parsedValue === "") {
        report.note = "empty in JSON";
        fillReport.push(report);
        return;
      }

      el.value = String(parsedValue);
      report.applied = el.value || null;

      if (!el.value) {
        report.note = "browser rejected value for input type";
      } else if (el.value !== String(parsedValue)) {
        report.note = "browser normalized value";
      }

      fillReport.push(report);
    });

    if (extraction.timezone) {
      fillReport.push({
        field: "timezone",
        parsed: String(extraction.timezone),
        applied: null,
        note: "not shown in form — calendar uses device TZ",
      });
    }

    console.log("SS to Cal form fill report:", fillReport);
    renderFillDebug(fillReport);
    updateFormUi();

    var form = document.getElementById("sstc-review-form");
    if (form) {
      form.addEventListener("input", updateFormUi);
      form.addEventListener("change", updateFormUi);
    }

    var calendarBtn = document.getElementById("sstc-calendar-btn");
    if (calendarBtn) {
      calendarBtn.addEventListener("click", function () {
        if (calendarBtn.disabled) {
          return;
        }
        /* Phase 5 — Google Calendar URL uses deviceTimezone() */
        console.log("SS to Cal: calendar button clicked (Phase 5 not wired yet)");
      });
    }
  }

  function renderFillDebug(fillReport) {
    var list = document.getElementById("sstc-debug-fill");
    if (!list) {
      return;
    }

    list.innerHTML = "";
    fillReport.forEach(function (item) {
      var li = document.createElement("li");
      var parsed = item.parsed == null ? "null" : item.parsed;
      var applied = item.applied == null ? "null" : item.applied;
      var extra = item.note ? " — " + item.note : "";
      li.textContent = item.field + ": parsed=" + parsed + ", in form=" + applied + extra;
      if (item.note && item.note.indexOf("rejected") !== -1) {
        li.className = "sstc-debug-fill-warn";
      }
      list.appendChild(li);
    });
  }

  registerServiceWorker();

  document.addEventListener("DOMContentLoaded", function () {
    initStandaloneUi();
    initShareForm();
  });
})();

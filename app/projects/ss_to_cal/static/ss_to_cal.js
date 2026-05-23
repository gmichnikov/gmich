(function () {
  "use strict";

  var FIELD_MAP = {
    title: "sstc-title",
    date: "sstc-date",
    startTime: "sstc-start-time",
    endTime: "sstc-end-time",
    location: "sstc-location",
    description: "sstc-description",
    timezone: "sstc-timezone",
  };

  var REQUIRED_FIELDS = ["title", "date"];
  var OPTIONAL_FIELDS = ["startTime", "endTime", "location", "description", "timezone"];

  var shareState = {
    confidence: null,
    modelTimezone: null,
    deviceTimezone: "",
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

  function isUncertainConfidence() {
    return shareState.confidence === "medium" || shareState.confidence === "low";
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
      if (!fieldValue(key)) {
        setFieldTag(key, "Required");
      } else {
        setFieldTag(key, null);
      }
    });

    OPTIONAL_FIELDS.forEach(function (key) {
      var verify = false;

      if (key === "timezone") {
        var tz = fieldValue("timezone");
        if (
          tz &&
          shareState.deviceTimezone &&
          tz !== shareState.deviceTimezone
        ) {
          verify = true;
        }
      }

      if (isUncertainConfidence()) {
        verify = true;
      }

      setFieldTag(key, verify ? "Please verify" : null);
    });

    var calendarBtn = document.getElementById("sstc-calendar-btn");
    if (calendarBtn) {
      var ready = fieldValue("title") && fieldValue("date");
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
    shareState.modelTimezone = extraction.timezone || null;
    shareState.deviceTimezone = deviceTimezone();

    console.log("SS to Cal parsed extraction:", extraction);

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

    var tzInput = document.getElementById("sstc-timezone");
    if (tzInput && !tzInput.value && shareState.deviceTimezone) {
      tzInput.value = shareState.deviceTimezone;
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
        /* Phase 5 — Google Calendar URL builder */
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

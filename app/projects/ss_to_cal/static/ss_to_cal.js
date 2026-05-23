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

  function isOnline() {
    return typeof navigator.onLine === "boolean" ? navigator.onLine : true;
  }

  function updateOfflineBanner() {
    var banner = document.getElementById("sstc-offline-banner");
    if (!banner) {
      return;
    }
    banner.hidden = isOnline();
  }

  function initOfflineUi() {
    updateOfflineBanner();
    window.addEventListener("online", updateOfflineBanner);
    window.addEventListener("offline", updateOfflineBanner);
  }

  function initErrorRecovery() {
    var goBackBtn = document.getElementById("sstc-go-back-btn");
    if (goBackBtn) {
      goBackBtn.addEventListener("click", function () {
        if (window.history.length > 1) {
          window.history.back();
        } else {
          window.location.href = "/ss-to-cal/";
        }
      });
    }

    var errorDataEl = document.getElementById("sstc-error-data");
    if (errorDataEl) {
      try {
        var errorData = JSON.parse(errorDataEl.textContent || "{}");
        if (errorData.error_code === "PARSE_FAILED") {
          console.warn("SS to Cal: PARSE_FAILED — check server logs for the raw model response");
        }
      } catch (err) {
        console.warn("SS to Cal: invalid error JSON", err);
      }
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

  function fieldValue(key) {
    var el = document.getElementById(FIELD_MAP[key]);
    if (!el) {
      return "";
    }
    return (el.value || "").trim();
  }

  /** Google Calendar "floating" stamp — no timezone; Google uses the user's TZ. */
  function formatGoogleFloatingStamp(dateStr, timeStr) {
    var dp = dateStr.split("-");
    var tp = timeStr.split(":");
    if (dp.length !== 3 || tp.length < 2) {
      return null;
    }
    var y = dp[0];
    var m = dp[1];
    var d = dp[2];
    var hh = tp[0];
    var mm = tp[1];
    if (!/^\d{4}$/.test(y) || !/^\d{2}$/.test(m) || !/^\d{2}$/.test(d)) {
      return null;
    }
    if (!/^\d{2}$/.test(hh) || !/^\d{2}$/.test(mm)) {
      return null;
    }
    return y + m + d + "T" + hh + mm + "00";
  }

  function isEndAfterStart() {
    var startTime = fieldValue("startTime");
    var endTime = fieldValue("endTime");
    if (!startTime || !endTime) {
      return true;
    }
    return endTime > startTime;
  }

  function buildGoogleCalendarUrl() {
    var title = fieldValue("title");
    var dateStr = fieldValue("date");
    var startTime = fieldValue("startTime");
    var endTime = fieldValue("endTime");
    var location = fieldValue("location");
    var description = fieldValue("description");

    var startStamp = formatGoogleFloatingStamp(dateStr, startTime);
    var endStamp = formatGoogleFloatingStamp(dateStr, endTime);
    if (!startStamp || !endStamp) {
      return null;
    }

    var params = new URLSearchParams();
    params.set("action", "TEMPLATE");
    params.set("text", title);
    params.set("dates", startStamp + "/" + endStamp);
    if (description) {
      params.set("details", description);
    }
    if (location) {
      params.set("location", location);
    }

    return "https://calendar.google.com/calendar/render?" + params.toString();
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
      if (key === "endTime") {
        if (!fieldValue(key)) {
          setFieldTag(key, "Required");
        } else if (!isEndAfterStart()) {
          setFieldTag(key, "Must be after start");
        } else {
          setFieldTag(key, null);
        }
      } else {
        setFieldTag(key, fieldValue(key) ? null : "Required");
      }
    });

    var calendarBtn = document.getElementById("sstc-calendar-btn");
    if (calendarBtn) {
      var ready =
        isOnline() &&
        REQUIRED_FIELDS.every(function (key) {
          return fieldValue(key);
        }) &&
        isEndAfterStart();
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
        var url = buildGoogleCalendarUrl();
        if (!url) {
          console.error("SS to Cal: failed to build Google Calendar URL");
          return;
        }
        console.log("SS to Cal: opening Google Calendar", url);
        var opened = window.open(url, "_blank");
        if (!opened) {
          window.location.href = url;
        }
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

  function initOfflineFormUi() {
    window.addEventListener("online", updateFormUi);
    window.addEventListener("offline", updateFormUi);
  }

  registerServiceWorker();

  document.addEventListener("DOMContentLoaded", function () {
    initStandaloneUi();
    initOfflineUi();
    initErrorRecovery();
    initShareForm();
    initOfflineFormUi();
  });
})();

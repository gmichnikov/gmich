(function () {
  "use strict";

  var SSTC_JS_VERSION = "2026-05-22-cal-debug-3";
  var CLIENT_LOG_URL = "/ss-to-cal/client-log";

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
    calendarReady: null,
  };

  function formatLogData(data) {
    if (data == null) {
      return "";
    }
    try {
      return JSON.stringify(data);
    } catch (err) {
      return String(data);
    }
  }

  function sstcLog(event, detail, data, level) {
    var timestamp = new Date().toLocaleTimeString();
    var line = timestamp + " " + event;
    if (detail) {
      line += " — " + detail;
    }
    var dataStr = formatLogData(data);
    if (dataStr) {
      line += " " + dataStr;
    }

    console.log("SS to Cal:", line);

    var list = document.getElementById("sstc-activity-log");
    if (list) {
      var item = document.createElement("li");
      item.textContent = line;
      if (level === "warn") {
        item.className = "sstc-activity-log-warn";
      } else if (level === "error") {
        item.className = "sstc-activity-log-error";
      }
      list.appendChild(item);
      if (list.children.length > 40) {
        list.removeChild(list.firstChild);
      }
      list.scrollTop = list.scrollHeight;
    }

    if (!navigator.sendBeacon) {
      return;
    }
    try {
      navigator.sendBeacon(
        CLIENT_LOG_URL,
        new Blob(
          [JSON.stringify({ event: event, detail: detail || "", data: data || null })],
          { type: "application/json" }
        )
      );
    } catch (err) {
      console.warn("SS to Cal: client log beacon failed", err);
    }
  }

  function readPageMeta() {
    var metaEl = document.getElementById("sstc-page-meta");
    if (!metaEl) {
      return null;
    }
    try {
      return JSON.parse(metaEl.textContent || "{}");
    } catch (err) {
      sstcLog("page_meta_parse_failed", err.message, null, "warn");
      return null;
    }
  }

  function calendarNotReadyReasons() {
    var reasons = [];
    REQUIRED_FIELDS.forEach(function (key) {
      if (!fieldValue(key)) {
        reasons.push("missing_" + key);
      }
    });
    if (fieldValue("startTime") && fieldValue("endTime") && !isEndAfterStart()) {
      reasons.push("end_before_start");
    }
    return reasons;
  }

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
        sstcLog("service_worker_registered", registration.scope);
        setSwStatus("Service worker registered (" + registration.scope + ").");
      })
      .catch(function (err) {
        sstcLog("service_worker_failed", err.message, null, "error");
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
    if (!/^\d{4}$/.test(y) || !/^\d{1,2}$/.test(m) || !/^\d{1,2}$/.test(d)) {
      return null;
    }
    if (!/^\d{1,2}$/.test(hh) || !/^\d{1,2}$/.test(mm)) {
      return null;
    }
    m = m.padStart(2, "0");
    d = d.padStart(2, "0");
    hh = hh.padStart(2, "0");
    mm = mm.padStart(2, "0");
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

  function openGoogleCalendar(url) {
    var standalone = isStandalone();
    sstcLog(
      "calendar_navigate",
      standalone ? "location.assign (standalone PWA)" : "window.open with fallback",
      { url: url, standalone: standalone }
    );

    if (standalone) {
      window.location.assign(url);
      return;
    }

    var opened = window.open(url, "_blank", "noopener,noreferrer");
    sstcLog("calendar_window_open", opened ? "returned window" : "blocked/null", { opened: !!opened });
    if (!opened) {
      window.location.assign(url);
    }
  }

  function showCalendarStatus(message, isError) {
    var el = document.getElementById("sstc-calendar-status");
    if (!el) {
      return;
    }
    el.textContent = message;
    el.hidden = false;
    el.classList.toggle("sstc-flash-error", !!isError);
    el.classList.toggle("sstc-flash-info", !isError);
  }

  function initCalendarButton() {
    var calendarBtn = document.getElementById("sstc-calendar-btn");
    if (!calendarBtn) {
      sstcLog("calendar_button_missing", "sstc-calendar-btn not found", null, "error");
      return;
    }
    if (calendarBtn.dataset.sstcBound === "1") {
      sstcLog("calendar_button_already_bound", "skipping duplicate listener");
      return;
    }
    calendarBtn.dataset.sstcBound = "1";
    sstcLog("calendar_button_bound", "click listener attached");

    calendarBtn.addEventListener("click", function () {
      sstcLog("calendar_click", calendarBtn.disabled ? "ignored — button disabled" : "processing", {
        disabled: calendarBtn.disabled,
        reasons: calendarNotReadyReasons(),
      });

      if (calendarBtn.disabled) {
        return;
      }

      var url = buildGoogleCalendarUrl();
      if (!url) {
        var fields = {
          title: fieldValue("title"),
          date: fieldValue("date"),
          startTime: fieldValue("startTime"),
          endTime: fieldValue("endTime"),
        };
        showCalendarStatus("Could not build the calendar link. Check date and times.", true);
        sstcLog("calendar_url_build_failed", "formatGoogleFloatingStamp returned null", fields, "error");
        return;
      }

      showCalendarStatus("Opening Google Calendar…", false);
      sstcLog("calendar_url_built", "navigating", { url: url });
      openGoogleCalendar(url);
    });
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
        REQUIRED_FIELDS.every(function (key) {
          return fieldValue(key);
        }) && isEndAfterStart();
      calendarBtn.disabled = !ready;

      if (shareState.calendarReady !== ready) {
        shareState.calendarReady = ready;
        if (ready) {
          sstcLog("calendar_button_enabled", "all required fields present");
        } else {
          sstcLog("calendar_button_disabled", "not ready", {
            reasons: calendarNotReadyReasons(),
          }, "warn");
        }
      }
    }
  }

  function initShareForm() {
    var dataEl = document.getElementById("sstc-extraction-data");
    if (!dataEl) {
      sstcLog("share_form_missing", "sstc-extraction-data not found", null, "warn");
      return;
    }

    var extraction = {};
    try {
      extraction = JSON.parse(dataEl.textContent || "{}");
    } catch (err) {
      sstcLog("extraction_json_invalid", err.message, null, "error");
      return;
    }

    shareState.confidence = extraction.confidence || null;
    sstcLog("extraction_loaded", "form prefill starting", {
      confidence: extraction.confidence,
      fields: Object.keys(extraction).filter(function (key) {
        return extraction[key] != null && extraction[key] !== "";
      }),
    });

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
    initCalendarButton();
    sstcLog("share_form_ready", "prefill complete", { fillReport: fillReport });

    var form = document.getElementById("sstc-review-form");
    if (form) {
      form.addEventListener("input", updateFormUi);
      form.addEventListener("change", updateFormUi);
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
    var pageMeta = readPageMeta();
    sstcLog("page_boot", "DOM ready", {
      jsVersion: SSTC_JS_VERSION,
      standalone: isStandalone(),
      navigatorOnLine: navigator.onLine,
      pageMeta: pageMeta,
      userAgent: navigator.userAgent,
    });

    initStandaloneUi();
    initErrorRecovery();
    initCalendarButton();
    initShareForm();
  });
})();

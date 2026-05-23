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
  }

  function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
      return;
    }

    navigator.serviceWorker
      .register("/ss-to-cal/sw.js", { scope: "/ss-to-cal/" })
      .catch(function (err) {
        console.warn("SS to Cal: service worker registration failed", err);
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
    if (isStandalone()) {
      window.location.assign(url);
      return;
    }

    var opened = window.open(url, "_blank", "noopener,noreferrer");
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
    if (!calendarBtn || calendarBtn.dataset.sstcBound === "1") {
      return;
    }
    calendarBtn.dataset.sstcBound = "1";

    calendarBtn.addEventListener("click", function () {
      if (calendarBtn.disabled) {
        return;
      }

      var url = buildGoogleCalendarUrl();
      if (!url) {
        showCalendarStatus("Could not build the calendar link. Check date and times.", true);
        console.error("SS to Cal: failed to build calendar URL", {
          date: fieldValue("date"),
          startTime: fieldValue("startTime"),
          endTime: fieldValue("endTime"),
        });
        return;
      }

      showCalendarStatus("Opening Google Calendar…", false);
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

    Object.keys(FIELD_MAP).forEach(function (key) {
      var el = document.getElementById(FIELD_MAP[key]);
      var parsedValue = extraction[key];
      if (!el || parsedValue == null || parsedValue === "") {
        return;
      }
      el.value = String(parsedValue);
    });

    renderFillDebug(extraction);
    updateFormUi();
    initCalendarButton();

    var form = document.getElementById("sstc-review-form");
    if (form) {
      form.addEventListener("input", updateFormUi);
      form.addEventListener("change", updateFormUi);
    }
  }

  function renderFillDebug(extraction) {
    var list = document.getElementById("sstc-debug-fill");
    if (!list) {
      return;
    }

    list.innerHTML = "";
    Object.keys(FIELD_MAP).forEach(function (key) {
      var el = document.getElementById(FIELD_MAP[key]);
      var parsedValue = extraction[key];
      var li = document.createElement("li");
      var parsed = parsedValue == null ? "null" : String(parsedValue);
      var applied = el && el.value ? el.value : "null";
      var note = "";
      if (parsedValue != null && parsedValue !== "" && el && !el.value) {
        note = " — browser rejected value for input type";
        li.className = "sstc-debug-fill-warn";
      }
      li.textContent = key + ": parsed=" + parsed + ", in form=" + applied + note;
      list.appendChild(li);
    });
  }

  registerServiceWorker();

  document.addEventListener("DOMContentLoaded", function () {
    initStandaloneUi();
    initErrorRecovery();
    initCalendarButton();
    initShareForm();
  });
})();

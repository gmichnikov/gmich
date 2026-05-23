(function () {
  "use strict";

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

    console.log("SS to Cal parsed extraction:", extraction);

    var fields = {
      title: "sstc-title",
      date: "sstc-date",
      startTime: "sstc-start-time",
      endTime: "sstc-end-time",
      location: "sstc-location",
      description: "sstc-description",
      timezone: "sstc-timezone",
    };

    var fillReport = [];

    Object.keys(fields).forEach(function (key) {
      var el = document.getElementById(fields[key]);
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
    if (tzInput && !tzInput.value) {
      try {
        tzInput.value = Intl.DateTimeFormat().resolvedOptions().timeZone;
      } catch (e) {
        /* ignore */
      }
    }

    console.log("SS to Cal form fill report:", fillReport);
    renderFillDebug(fillReport);
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

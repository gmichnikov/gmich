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

  registerServiceWorker();

  document.addEventListener("DOMContentLoaded", function () {
    initStandaloneUi();
  });
})();

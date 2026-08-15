(function (global) {
  var DAY_COLORS = {
    1: "#c62828",
    2: "#6a1b9a",
    3: "#00897b",
    4: "#ef6c00",
    5: "#3949ab",
    other: "#6d4c41",
  };

  var photoBaseUrl = "";

  function escapeHtml(text) {
    var el = document.createElement("div");
    el.textContent = text;
    return el.innerHTML;
  }

  function dayLabel(day) {
    if (day === "other") {
      return "Other";
    }
    return "Day " + day;
  }

  function popupHtml(place) {
    var badge =
      place.kind === "hotel" ? "Hotel" : dayLabel(place.day);
    var toneClass =
      place.kind === "hotel"
        ? "japan-recs-popup--hotel"
        : "japan-recs-popup--day-" + place.day;

    var html =
      '<div class="japan-recs-popup ' +
      toneClass +
      '">' +
      '<strong class="japan-recs-popup-title">' +
      escapeHtml(place.name) +
      "</strong>" +
      '<span class="japan-recs-popup-day">' +
      escapeHtml(badge) +
      "</span>";

    if (place.photoKey && photoBaseUrl) {
      html +=
        '<img class="japan-recs-popup-photo" src="' +
        escapeHtml(photoBaseUrl + place.photoKey) +
        '" alt="' +
        escapeHtml(place.name) +
        '" loading="lazy" hidden onload="this.hidden=false" onerror="this.remove()">';
    } else if (place.qrSrc) {
      html +=
        '<img class="japan-recs-popup-qr" src="' +
        escapeHtml(place.qrSrc) +
        '" width="148" height="148" alt="QR code for Google Maps">';
    }

    html += '<div class="japan-recs-popup-links">';
    if (place.mapsUrl) {
      html +=
        '<a class="japan-recs-popup-link" href="' +
        escapeHtml(place.mapsUrl) +
        '" target="_blank" rel="noopener noreferrer">Open in Google Maps</a>';
    }
    if (place.websiteUrl) {
      html +=
        '<a class="japan-recs-popup-link" href="' +
        escapeHtml(place.websiteUrl) +
        '" target="_blank" rel="noopener noreferrer">Website</a>';
    }
    if (place.wikipediaUrl) {
      html +=
        '<a class="japan-recs-popup-link" href="' +
        escapeHtml(place.wikipediaUrl) +
        '" target="_blank" rel="noopener noreferrer">Wikipedia</a>';
    }
    html += "</div></div>";
    return html;
  }

  function markerIcon(day) {
    return L.divIcon({
      className: "japan-recs-marker-icon",
      html:
        '<div class="japan-recs-marker-pin japan-recs-marker-pin--day-' +
        day +
        '" aria-hidden="true">' +
        '<svg viewBox="0 0 28 40" focusable="false">' +
        '<path fill="currentColor" d="M14 0C6.268 0 0 6.268 0 14c0 10.5 14 26 14 26s14-15.5 14-26C28 6.268 21.732 0 14 0zm0 19a5 5 0 1 1 0-10 5 5 0 0 1 0 10z"/>' +
        "</svg></div>",
      iconSize: [28, 40],
      iconAnchor: [14, 40],
      popupAnchor: [0, -36],
    });
  }

  function hotelIcon() {
    return L.divIcon({
      className: "japan-recs-marker-icon",
      html:
        '<div class="japan-recs-hotel-marker" aria-hidden="true">' +
        '<svg viewBox="0 0 40 40" focusable="false">' +
        '<circle cx="20" cy="20" r="18" fill="#ffffff" stroke="#333333" stroke-width="2"/>' +
        '<path fill="#333333" d="M11 27V15.5c0-.8.7-1.5 1.5-1.5H16v-1.2c0-.7.6-1.3 1.3-1.3h5.4c.7 0 1.3.6 1.3 1.3V14h3.5c.8 0 1.5.7 1.5 1.5V27h-2.2v-2.2H13.2V27H11zm2.2-4.4h13.6v-7.1h-2.3V18h-2.2v-2.5h-4.8V18h-2.2v-2.5h-2.1v7.1z"/>' +
        "</svg></div>",
      iconSize: [40, 40],
      iconAnchor: [20, 20],
      popupAnchor: [0, -18],
    });
  }

  function createLayer(place, index) {
    var popupOptions = {
      className: "japan-recs-leaflet-popup",
      maxWidth: place.photoKey ? 280 : 220,
    };
    var layer;

    if (place.path && place.path.length) {
      layer = L.polyline(place.path, {
        color: DAY_COLORS[place.day] || "#333",
        weight: 5,
        opacity: 0.9,
        lineJoin: "round",
        lineCap: "round",
        className: "japan-recs-path japan-recs-path--day-" + place.day,
      });
    } else if (place.kind === "hotel") {
      layer = L.marker([place.lat, place.lng], {
        icon: hotelIcon(),
        zIndexOffset: 500,
      });
    } else {
      layer = L.marker([place.lat, place.lng], {
        icon: markerIcon(place.day),
      });
    }

    layer.bindPopup(popupHtml(place), popupOptions);
    layer._japanRecsDay = place.day || null;
    layer._japanRecsIndex = index;
    return layer;
  }

  function fitToLayers(map, layers) {
    if (!layers.length) {
      return;
    }
    if (layers.length === 1 && layers[0].getLatLng) {
      map.setView(layers[0].getLatLng(), 15);
      return;
    }
    var group = L.featureGroup(layers);
    map.fitBounds(group.getBounds(), { padding: [56, 56], maxZoom: 15 });
  }

  function focusLayer(map, layer) {
    if (layer.getLatLng) {
      map.setView(layer.getLatLng(), Math.max(map.getZoom(), 15));
    } else if (layer.getBounds) {
      map.fitBounds(layer.getBounds(), { padding: [80, 80], maxZoom: 16 });
    }
    layer.openPopup();
  }

  function init(config) {
    var mapEl = config.mapEl;
    var filterEl = config.filterEl;
    var listEl = config.listEl;
    var places = config.places || [];
    var alwaysPlaces = config.alwaysPlaces || [];
    var dayOrder = config.dayOrder || [];
    var fallbackView = config.fallbackView;

    if (!mapEl || !filterEl || !listEl || !global.L) {
      return;
    }

    photoBaseUrl =
      config.photoBaseUrl ||
      mapEl.getAttribute("data-photo-base") ||
      "/japan-recs/photos/";

    var listBody = listEl.querySelector(".japan-recs-place-list-scroll");
    var listHandle = listEl.querySelector(".japan-recs-place-list-handle");
    var listCountEl = listEl.querySelector(".japan-recs-place-list-handle-count");
    if (!listBody) {
      return;
    }

    var map = L.map(mapEl, { scrollWheelZoom: true });
    L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          "Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom",
      }
    ).addTo(map);

    var layersByDay = {};
    dayOrder.forEach(function (day) {
      layersByDay[day] = [];
    });

    var placeEntries = [];
    var dayLayers = [];

    places.forEach(function (place, index) {
      var layer = createLayer(place, index);
      placeEntries.push({ place: place, layer: layer, index: index });
      layersByDay[place.day].push(layer);
      dayLayers.push(layer);

      layer.on("popupopen", function () {
        setActiveIndex(index);
      });
    });

    alwaysPlaces.forEach(function (place) {
      createLayer(place, -1).addTo(map);
    });

    var currentDay = "all";
    var activeIndex = null;

    function visibleEntries(dayFilter) {
      if (dayFilter === "all") {
        return placeEntries.slice();
      }
      return placeEntries.filter(function (entry) {
        return entry.place.day === dayFilter;
      });
    }

    function visibleDayLayers(dayFilter) {
      if (dayFilter === "all") {
        return dayLayers;
      }
      return layersByDay[dayFilter] || [];
    }

    function setActiveIndex(index) {
      activeIndex = index;
      listBody.querySelectorAll(".japan-recs-place-item").forEach(function (btn) {
        var isActive = btn.getAttribute("data-index") === String(index);
        btn.classList.toggle("is-active", isActive);
        if (isActive) {
          btn.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
      });
    }

    function clearActiveIndex() {
      activeIndex = null;
      listBody.querySelectorAll(".japan-recs-place-item.is-active").forEach(function (btn) {
        btn.classList.remove("is-active");
      });
    }

    function appendPlaceItem(entry) {
      var place = entry.place;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className =
        "japan-recs-place-item japan-recs-place-item--day-" + place.day;
      if (place.path && place.path.length) {
        btn.classList.add("japan-recs-place-item--route");
      }
      btn.setAttribute("data-index", String(entry.index));
      btn.setAttribute("role", "listitem");
      btn.innerHTML =
        '<span class="japan-recs-place-item-dot" aria-hidden="true"></span>' +
        '<span class="japan-recs-place-item-name">' +
        escapeHtml(place.name) +
        "</span>";
      listBody.appendChild(btn);
      if (activeIndex === entry.index) {
        btn.classList.add("is-active");
      }
      return btn;
    }

    function renderPlaceList(dayFilter) {
      listBody.innerHTML = "";
      var entries = visibleEntries(dayFilter);

      if (listCountEl) {
        listCountEl.textContent =
          entries.length === 1 ? "1 place" : entries.length + " places";
      }

      if (dayFilter === "all") {
        dayOrder.forEach(function (day) {
          var dayEntries = entries.filter(function (entry) {
            return entry.place.day === day;
          });
          if (!dayEntries.length) {
            return;
          }
          var heading = document.createElement("div");
          heading.className =
            "japan-recs-place-list-heading japan-recs-place-list-heading--day-" +
            day;
          heading.textContent = dayLabel(day);
          listBody.appendChild(heading);
          dayEntries.forEach(appendPlaceItem);
        });
      } else {
        entries.forEach(appendPlaceItem);
      }
    }

    function applyDayFilter(dayFilter) {
      currentDay = dayFilter;
      map.closePopup();
      clearActiveIndex();

      dayLayers.forEach(function (layer) {
        map.removeLayer(layer);
      });

      var shown = visibleDayLayers(dayFilter);
      shown.forEach(function (layer) {
        layer.addTo(map);
      });
      fitToLayers(map, shown);
      if (!shown.length && fallbackView) {
        map.setView(fallbackView.center, fallbackView.zoom);
      }

      filterEl.querySelectorAll(".japan-recs-day-btn").forEach(function (btn) {
        var active = btn.getAttribute("data-day") === String(dayFilter);
        btn.classList.toggle("is-active", active);
        btn.setAttribute("aria-pressed", active ? "true" : "false");
      });

      renderPlaceList(dayFilter);
      map.invalidateSize();
    }

    filterEl.addEventListener("click", function (event) {
      var btn = event.target.closest(".japan-recs-day-btn");
      if (!btn) {
        return;
      }
      var day = btn.getAttribute("data-day");
      if (!day || day === currentDay) {
        return;
      }
      applyDayFilter(day);
    });

    listBody.addEventListener("click", function (event) {
      var item = event.target.closest(".japan-recs-place-item");
      if (!item) {
        return;
      }
      var index = Number(item.getAttribute("data-index"));
      var entry = placeEntries[index];
      if (!entry) {
        return;
      }
      focusLayer(map, entry.layer);
      setActiveIndex(index);
      if (window.matchMedia("(max-width: 767px)").matches) {
        listEl.classList.remove("is-open");
        if (listHandle) {
          listHandle.setAttribute("aria-expanded", "false");
        }
      }
    });

    if (listHandle) {
      listHandle.addEventListener("click", function () {
        var open = listEl.classList.toggle("is-open");
        listHandle.setAttribute("aria-expanded", open ? "true" : "false");
        window.setTimeout(function () {
          map.invalidateSize();
        }, 250);
      });
    }

    applyDayFilter("all");
  }

  global.JapanRecsMap = { init: init };
})(window);

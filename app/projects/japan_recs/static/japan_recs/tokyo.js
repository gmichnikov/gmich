(function () {
  var mapEl = document.getElementById("japan-recs-map");
  var filterEl = document.querySelector(".japan-recs-day-filter");
  if (!mapEl || !filterEl || !window.L) {
    return;
  }

  var DAY_COLORS = {
    1: "#c62828",
    2: "#6a1b9a",
    3: "#00897b",
    4: "#ef6c00",
    5: "#3949ab",
    other: "#6d4c41",
  };

  var places = [
    {
      name: "Asakusa Shrine",
      day: "1",
      lat: 35.7151389,
      lng: 139.7974361,
      mapsUrl: "https://maps.app.goo.gl/NGLLqcTNW9ixPg9aA",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Asakusa_Shrine",
    },
    {
      name: "Maguro-to-Shari Asakusa",
      day: "1",
      lat: 35.71333009937878,
      lng: 139.79358809614266,
      mapsUrl: "https://maps.app.goo.gl/HbT94E95YzbNdoko9",
      websiteUrl: "https://maguroshari.com/",
    },
    {
      name: "Meiji Jingu Shrine",
      day: "2",
      lat: 35.67611,
      lng: 139.69917,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Meiji+Jingu+Shrine",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Meiji_Shrine",
    },
    {
      name: "TsuruTonTan UDON NOODLE Brasserie SHIBUYA",
      day: "2",
      lat: 35.65844671780108,
      lng: 139.70216436918733,
      mapsUrl: "https://maps.app.goo.gl/kyTFpfF8RCHmJPim7",
    },
    {
      name: "Shibuya Crossing",
      day: "2",
      lat: 35.659526051399624,
      lng: 139.7005449531125,
      mapsUrl: "https://maps.app.goo.gl/zMBQ4gqaAXY2NEdo7",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Shibuya_Crossing",
    },
    {
      name: "Tsukiji Peppers Cafe",
      day: "3",
      lat: 35.66527717036475,
      lng: 139.77015429380677,
      mapsUrl: "https://maps.app.goo.gl/DKihSHcYR2Zd5tZJ7",
      websiteUrl: "https://pepperscafe.tokyo/",
    },
    {
      name: "Tsukiji Outer Market",
      day: "3",
      lat: 35.664762572100486,
      lng: 139.7703117571338,
      mapsUrl: "https://maps.app.goo.gl/eKcKTy6bsr7yR9dz8",
      websiteUrl: "https://www.tsukiji.or.jp/english/",
    },
    {
      name: "BREIZH Café Crêperie Shinjuku Takashimaya",
      day: "4",
      lat: 35.6878526686546,
      lng: 139.70226976176534,
      mapsUrl: "https://maps.app.goo.gl/e13kbJus2xHx1ezv8",
      websiteUrl: "https://le-bretagne.com/creperie/shinjuku/",
    },
    {
      name: "Ginza Kagari - Soba",
      day: "4",
      lat: 35.671185268828545,
      lng: 139.76135095452554,
      mapsUrl: "https://maps.app.goo.gl/BQEmFVC4SUJDWDhb9",
      websiteUrl: "https://ginzakagari.thebase.in/",
    },
    {
      name: "Wagyu Yakiniku Ten Gamushara Akasaka",
      day: "5",
      lat: 35.66676082007621,
      lng: 139.73997943956655,
      mapsUrl: "https://maps.app.goo.gl/v5npXsthsUZGbwKX8",
      websiteUrl: "https://www.gamushara.info/",
    },
    {
      name: "Asakusa Gyukatsu",
      day: "5",
      lat: 35.71078791485017,
      lng: 139.79596854929756,
      mapsUrl: "https://maps.app.goo.gl/rnC86bXAoXVCA8bC6",
      websiteUrl: "https://tabelog.com/en/tokyo/A1311/A131102/13172454/",
    },
    {
      name: "teamLab Planets",
      day: "5",
      lat: 35.649034782877116,
      lng: 139.78999048131445,
      mapsUrl: "https://maps.app.goo.gl/pNW2r1RZusR7R6zDA",
      websiteUrl: "https://www.teamlab.art/jp/e/planets/",
    },
    {
      name: "Tokyo Skytree",
      day: "5",
      lat: 35.7100516905249,
      lng: 139.81070273748836,
      mapsUrl: "https://maps.app.goo.gl/moVsrRfDd3A2Ldn68",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Tokyo_Skytree",
    },
    {
      name: "Isetan Shinjuku",
      day: "other",
      lat: 35.69161873077868,
      lng: 139.70465230960664,
      mapsUrl: "https://maps.app.goo.gl/MtyVPRcMgUWm2RWZ8",
      websiteUrl: "https://www.jocjapantravel.com/tokyo-shinjuku-isetan-food-floor/",
    },
  ];

  var alwaysPlaces = [
    {
      name: "Shangri-La Tokyo",
      kind: "hotel",
      lat: 35.682454369693914,
      lng: 139.76938322245218,
      mapsUrl: "https://maps.app.goo.gl/JicBADWAAyFbtd2JA",
    },
  ];

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

    if (place.qrSrc) {
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

  function createLayer(place) {
    var popupOptions = {
      className: "japan-recs-leaflet-popup",
      maxWidth: 220,
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
    return layer;
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

  var layersByDay = { 1: [], 2: [], 3: [], 4: [], 5: [], other: [] };
  var dayLayers = [];

  places.forEach(function (place) {
    var layer = createLayer(place);
    layersByDay[place.day].push(layer);
    dayLayers.push(layer);
  });

  alwaysPlaces.forEach(function (place) {
    createLayer(place).addTo(map);
  });

  var currentDay = "all";

  function visibleDayLayers(dayFilter) {
    if (dayFilter === "all") {
      return dayLayers;
    }
    return layersByDay[dayFilter] || [];
  }

  function fitToLayers(layers) {
    if (!layers.length) {
      map.setView([35.6762, 139.6503], 12);
      return;
    }
    if (layers.length === 1 && layers[0].getLatLng) {
      map.setView(layers[0].getLatLng(), 15);
      return;
    }
    var group = L.featureGroup(layers);
    map.fitBounds(group.getBounds(), { padding: [56, 56], maxZoom: 15 });
  }

  function applyDayFilter(dayFilter) {
    currentDay = dayFilter;
    map.closePopup();

    dayLayers.forEach(function (layer) {
      map.removeLayer(layer);
    });

    var shown = visibleDayLayers(dayFilter);
    shown.forEach(function (layer) {
      layer.addTo(map);
    });
    fitToLayers(shown);

    filterEl.querySelectorAll(".japan-recs-day-btn").forEach(function (btn) {
      var active = btn.getAttribute("data-day") === String(dayFilter);
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    });
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

  applyDayFilter("all");
})();

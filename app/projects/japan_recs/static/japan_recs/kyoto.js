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
    other: "#6d4c41",
  };

  var places = [
    {
      name: "Arashiyama Monkey Park Iwatayama",
      day: "1",
      lat: 35.008938,
      lng: 135.674681,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Arashiyama+Monkey+Park+Iwatayama",
      qrSrc: mapEl.dataset.monkeyQr,
    },
    {
      name: "Arashiyama Bamboo Forest",
      day: "1",
      lat: 35.016742,
      lng: 135.671148,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Arashiyama+Bamboo+Forest",
      qrSrc: mapEl.dataset.bambooQr,
    },
    {
      name: "Sabanji Ramen",
      day: "1",
      lat: 35.03742193700756,
      lng: 135.73078304235545,
      mapsUrl: "https://maps.app.goo.gl/6pHjonZUveMKox7a8",
      websiteUrl: "https://sabanji.com/en/index.html",
    },
    {
      name: "Kinkaku-ji (Golden Pavilion)",
      day: "1",
      lat: 35.0395,
      lng: 135.7285,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Kinkaku-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Kinkaku-ji",
    },
    {
      name: "Ginkaku-ji (Silver Pavilion)",
      day: "2",
      lat: 35.02667,
      lng: 135.79833,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Ginkaku-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Ginkaku-ji",
    },
    {
      name: "Omen Ginkaku-ji Udon",
      day: "2",
      lat: 35.02625018718538,
      lng: 135.79494026483994,
      mapsUrl: "https://maps.app.goo.gl/ZW3pJUCb4UYFARy29",
      websiteUrl: "https://omen.co.jp",
    },
    {
      name: "Philosopher's Path",
      day: "2",
      // Approximate canal route from near Ginkaku-ji south toward Nanzen-ji
      path: [
        [35.0261, 135.79635],
        [35.0248, 135.79655],
        [35.0232, 135.7964],
        [35.0215, 135.79605],
        [35.0198, 135.79565],
        [35.018, 135.79525],
        [35.0162, 135.79485],
        [35.0145, 135.79445],
        [35.0129, 135.7941],
        [35.0117, 135.7937],
      ],
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Philosopher%27s+Path+Kyoto",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Philosopher%27s_Walk",
    },
    {
      name: "Nanzen-ji",
      day: "2",
      lat: 35.01139,
      lng: 135.79417,
      mapsUrl:
        "https://www.google.com/maps/search/?api=1&query=Nanzen-ji",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Nanzen-ji",
    },
    {
      name: "Kyoto Tonkatsu Katsuda Shijokarasuma",
      day: "2",
      lat: 35.00126103247668,
      lng: 135.75944064822355,
      mapsUrl: "https://maps.app.goo.gl/zsGsidgpZU48C8Bw6",
      websiteUrl: "https://chikayado.jp/tonkatsukarasuma?_src=gbpmenu",
    },
    {
      name: "Nijō Castle",
      day: "3",
      lat: 35.014168,
      lng: 135.747498,
      mapsUrl: "https://maps.app.goo.gl/6sH5GopS6KWrYzAE8",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Nijo_Castle",
    },
    {
      name: "Sushiro",
      day: "3",
      lat: 35.003741208208695,
      lng: 135.77421649564323,
      mapsUrl: "https://maps.app.goo.gl/djTVTXmPtW6pjcdb9",
      websiteUrl: "https://www.akindo-sushiro.co.jp/en/",
    },
    {
      name: "Nishiki Market",
      day: "3",
      lat: 35.00502620357052,
      lng: 135.7646169064146,
      mapsUrl: "https://maps.app.goo.gl/LkuRck4Vr7ze1y3M8",
      websiteUrl: "https://www.kyoto-nishiki.or.jp/en/",
    },
    {
      name: "Kiyomizu-dera",
      day: "3",
      lat: 34.995,
      lng: 135.785,
      mapsUrl: "https://maps.app.goo.gl/UFf46S5F7fPuSQFe6",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Kiyomizu-dera",
    },
    {
      name: "Fushimi Inari Taisha",
      day: "3",
      lat: 34.96722,
      lng: 135.77278,
      mapsUrl: "https://maps.app.goo.gl/qJHzAtWBRsJyTYxZA",
      wikipediaUrl: "https://en.wikipedia.org/wiki/Fushimi_Inari-taisha",
    },
    {
      name: "Sushi no Musashi - Kyoto Station",
      day: "other",
      lat: 34.9846715476842,
      lng: 135.75940259330807,
      mapsUrl: "https://maps.app.goo.gl/qNn18kt4miKSM5zV7",
      websiteUrl: "https://sushinomusashi.com/",
    },
    {
      name: "Boulangerie Cherish",
      day: "other",
      lat: 34.98793077291315,
      lng: 135.74112171849868,
      mapsUrl: "https://maps.app.goo.gl/N7ygAy7Ai3SUtc849",
    },
  ];

  var alwaysPlaces = [
    {
      name: "Dusit Thani Kyoto",
      kind: "hotel",
      lat: 34.99193355895671,
      lng: 135.7551218308406,
      mapsUrl: "https://maps.app.goo.gl/xkqzNPgZzgDWqcg17",
      websiteUrl: "https://www.dusit.com/dusitthani-kyoto/ja/",
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
      place.kind === "hotel"
        ? "Hotel"
        : dayLabel(place.day);
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
    layer._japanRecsAlways = !!place.kind && place.kind === "hotel";
    return layer;
  }

  var map = L.map(mapEl, { scrollWheelZoom: true });
  // Esri World Street Map favors English / romanized labels in Japan
  // (default OSM tiles render Japanese characters).
  L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    {
      maxZoom: 19,
      attribution:
        "Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom",
    }
  ).addTo(map);

  var layersByDay = { 1: [], 2: [], 3: [], other: [] };
  var dayLayers = [];
  var alwaysLayers = [];

  places.forEach(function (place) {
    var layer = createLayer(place);
    layersByDay[place.day].push(layer);
    dayLayers.push(layer);
  });

  alwaysPlaces.forEach(function (place) {
    var layer = createLayer(place);
    alwaysLayers.push(layer);
    layer.addTo(map);
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
    // Hotel stays on the map; fit to the day selection only
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

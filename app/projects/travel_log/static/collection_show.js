/**
 * Collection show: List / Map tabs, Leaflet loaded only when Map is opened.
 * Map markers follow the same filters as the list (tlog-collection-filters-changed).
 */
(function () {
    var tabsRoot = document.getElementById("tlog-view-tabs");
    var listPanel = document.getElementById("tlog-view-list");
    var mapPanel = document.getElementById("tlog-view-map");
    var mapEl = document.getElementById("tlog-collection-map");
    var tabListBtn = document.getElementById("tlog-tab-list");
    var tabMapBtn = document.getElementById("tlog-tab-map");
    var tabCalBtn = document.getElementById("tlog-tab-calendar");
    var calPanel = document.getElementById("tlog-view-calendar");

    if (!tabsRoot || !listPanel || !mapPanel || !tabListBtn || !tabMapBtn) {
        return;
    }

    var hasCalendarTab = !!(calPanel && tabCalBtn);

    var map = null;
    var markersLayer = null;
    var markersByEntryId = new Map();
    var leafletLoading = null;
    var mapInitialized = false;
    var currentView = "list";

    function loadScript(src) {
        return new Promise(function (resolve, reject) {
            var s = document.createElement("script");
            s.src = src;
            s.onload = resolve;
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }

    function loadLeaflet() {
        if (window.L) {
            return Promise.resolve();
        }
        if (leafletLoading) {
            return leafletLoading;
        }
        var css = document.createElement("link");
        css.rel = "stylesheet";
        css.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
        document.head.appendChild(css);
        leafletLoading = loadScript("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js").then(function () {
            leafletLoading = null;
        });
        return leafletLoading;
    }

    function escapeHtml(s) {
        if (!s) {
            return "";
        }
        var d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    /** Allow only #rgb / #rrggbb for inline marker color (XSS-safe). */
    function sanitizeHexColor(s) {
        if (!s || typeof s !== "string") {
            return "";
        }
        var t = s.trim();
        return /^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$/.test(t) ? t : "";
    }

    /** Stable hue from tag ids when no custom tag color. */
    function hueFromTagIds(tagIdsStr) {
        var ids = (tagIdsStr || "").split(",").filter(Boolean);
        if (ids.length === 0) {
            return 221;
        }
        var sum = 0;
        for (var i = 0; i < ids.length; i++) {
            var n = parseInt(ids[i], 10);
            if (!isNaN(n)) {
                sum += n * (17 + i * 3);
            }
        }
        return Math.abs(sum) % 360;
    }

    function markerFillColor(bgAttr, tagIdsStr) {
        var hex = sanitizeHexColor(bgAttr || "");
        if (hex) {
            return hex;
        }
        var h = hueFromTagIds(tagIdsStr);
        return "hsl(" + h + ", 62%, 46%)";
    }

    function markerLetterColor(contrastAttr) {
        return contrastAttr === "dark" ? "#1f2937" : "#ffffff";
    }

    /**
     * SVG path data for common map POI types (Material-style silhouettes, readable at ~15px).
     */
    var MAP_POI_PATHS = {
        pin: "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z",
        food: "M11 9H9V2H7v7H5V2H3v7c0 2.12 1.66 3.84 3.75 3.97V22h2.5v-9.03C11.34 12.84 13 11.12 13 9V2h-2v7zm5-3v8h2.5v8H21V2c-2.76 0-5 2.24-5 4z",
        coffee:
            "M20 3H4v10c0 2.21 1.79 4 4 4h6c2.21 0 4-1.79 4-4v-3h2c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 5h-2V5h2v3zM2 21h20v2H2v-2z",
        bar: "M21 5V3H3v2l8 9v5H6v2h12v-2h-5v-5l9-9zM7.43 7L5.66 5h12.69l-1.78 2H7.43z",
        shop: "M18 6h-2c0-1.1-.9-2-2-2H10c-1.1 0-2 .9-2 2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-6-1c.55 0 1 .45 1 1v1h-2V6c0-.55.45-1 1-1zm6 12H6V9h2v1c0 .55.45 1 1 1h6c.55 0 1-.45 1-1V9h2v8z",
        museum:
            "M4 10v7h3v-7H4zm6 0v7h3v-7h-3zM2 22h19v-3H2v3zm8-18h3v3h-3V4zM16.5 2h-9L9 4h6l-.5-2zM6 4v3h3V4H6zm10 0v3h3V4h-3zM2 5v2h19V5H2z",
        sight:
            "M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z",
        park: "M14 6l-3.75 5 2.85 3.8-1.6 1.2C9.81 13.75 7 10 7 10l-6 8h22L14 6z",
        hotel:
            "M7 13c1.66 0 3-1.34 3-3S8.66 7 7 7s-3 1.34-3 3 1.34 3 3 3zm12-6h-8v7H3V5H1v15h2v-3h18v3h2v-9c0-2.21-1.79-4-4-4z",
        flight:
            "M10.18 9h2.64L12 6.18 10.18 9zM20 20v-2H4v2h16zm-4-9h2v3h-2v-3zM6 11h2v3H6v-3zm2-5h8l4 8H4l4-8z",
        train:
            "M12 2c-4 0-8 .5-8 4v9.5C4 17.43 5.57 19 7.5 19L6 20.5v.5h2.23l2-2H14l2 2h2v-.5L16.5 19c1.93 0 3.5-1.57 3.5-3.5V6c0-3.5-3-4-8-4zM7.5 17c-.83 0-1.5-.67-1.5-1.5S6.67 14 7.5 14s1.5.67 1.5 1.5S8.33 17 7.5 17zm3.5-6H9V9h2v2zm5.5 6c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zm1.5-6h-2V9h2v2z",
    };

    var TAG_CATEGORY_RULES = [
        [/coffee|cafe|espresso|latte/i, "coffee"],
        [/beer|brew|pub|bar\b|wine|winery|cocktail/i, "bar"],
        [/bakery|bake|pastry|dessert|cake|food|restaurant|dinner|lunch|brunch|eat|dining/i, "food"],
        [/shop|store|mall|market|boutique|retail/i, "shop"],
        [/museum|gallery|exhibit/i, "museum"],
        [/\bsight\b|\bsights\b|sightseeing|viewpoint|lookout|vista|panorama/i, "sight"],
        [/park|hike|trail|nature|garden|camp|outdoor/i, "park"],
        [/hotel|lodging|stay|resort|bnb|hostel/i, "hotel"],
        [/beach|ocean|coast|island|surf/i, "park"],
        [/flight|airport|plane|flying/i, "flight"],
        [/train|station|rail|subway|metro/i, "train"],
    ];

    function poiCategoryFromTagName(firstTagName) {
        if (!firstTagName || !String(firstTagName).trim()) {
            return null;
        }
        var name = String(firstTagName);
        for (var i = 0; i < TAG_CATEGORY_RULES.length; i++) {
            if (TAG_CATEGORY_RULES[i][0].test(name)) {
                return TAG_CATEGORY_RULES[i][1];
            }
        }
        return null;
    }

    function svgPoiIcon(pathD) {
        return (
            '<svg class="tlog-map-marker-svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="' +
            pathD +
            '"></path></svg>'
        );
    }

    function markerInnerHtml(firstTagName, letterContrastAttr) {
        var color = markerLetterColor(letterContrastAttr || "");
        var wrap =
            '<span class="tlog-map-marker-icon-wrap" style="color:' + color + '">';
        var cat = poiCategoryFromTagName(firstTagName);
        if (cat && MAP_POI_PATHS[cat]) {
            return wrap + svgPoiIcon(MAP_POI_PATHS[cat]) + "</span>";
        }
        if (firstTagName && String(firstTagName).trim()) {
            var letter = String(firstTagName).trim().charAt(0).toUpperCase();
            if (/[A-Za-z0-9]/.test(letter)) {
                return (
                    wrap +
                    '<span class="tlog-map-marker-letter">' +
                    escapeHtml(letter) +
                    "</span></span>"
                );
            }
        }
        return wrap + svgPoiIcon(MAP_POI_PATHS.pin) + "</span>";
    }

    function createTagMarkerIcon(
        L,
        bgAttr,
        tagIdsStr,
        firstTagName,
        letterContrastAttr
    ) {
        var fill = markerFillColor(bgAttr, tagIdsStr);
        var inner = markerInnerHtml(firstTagName, letterContrastAttr);
        var html =
            '<div class="tlog-map-marker-pin" style="--tlog-marker-fill:' +
            fill +
            '">' +
            inner +
            "</div>";
        return L.divIcon({
            html: html,
            className: "tlog-map-marker-divicon",
            iconSize: [30, 30],
            iconAnchor: [15, 15],
            popupAnchor: [0, -12],
        });
    }

    function setPanelVisible(panel, visible) {
        if (visible) {
            panel.classList.remove("tlog-hidden");
            panel.removeAttribute("hidden");
        } else {
            panel.classList.add("tlog-hidden");
            panel.setAttribute("hidden", "hidden");
        }
    }

    function setView(view) {
        currentView = view;
        if (hasCalendarTab) {
            setPanelVisible(listPanel, view === "list");
            setPanelVisible(calPanel, view === "calendar");
            setPanelVisible(mapPanel, view === "map");
            tabListBtn.classList.toggle("tlog-view-tab-active", view === "list");
            tabCalBtn.classList.toggle("tlog-view-tab-active", view === "calendar");
            tabMapBtn.classList.toggle("tlog-view-tab-active", view === "map");
            tabListBtn.setAttribute("aria-selected", view === "list" ? "true" : "false");
            tabCalBtn.setAttribute("aria-selected", view === "calendar" ? "true" : "false");
            tabMapBtn.setAttribute("aria-selected", view === "map" ? "true" : "false");
            return;
        }
        if (view === "list") {
            setPanelVisible(listPanel, true);
            setPanelVisible(mapPanel, false);
            tabListBtn.classList.add("tlog-view-tab-active");
            tabMapBtn.classList.remove("tlog-view-tab-active");
            tabListBtn.setAttribute("aria-selected", "true");
            tabMapBtn.setAttribute("aria-selected", "false");
        } else {
            setPanelVisible(listPanel, false);
            setPanelVisible(mapPanel, true);
            tabListBtn.classList.remove("tlog-view-tab-active");
            tabMapBtn.classList.add("tlog-view-tab-active");
            tabListBtn.setAttribute("aria-selected", "false");
            tabMapBtn.setAttribute("aria-selected", "true");
        }
    }

    function buildMarkers() {
        if (!markersLayer || !window.L) {
            return;
        }
        markersLayer.clearLayers();
        markersByEntryId.clear();
        document.querySelectorAll(".tlog-entry-item").forEach(function (li) {
            var latStr = li.getAttribute("data-lat") || "";
            var lngStr = li.getAttribute("data-lng") || "";
            if (!latStr || !lngStr) {
                return;
            }
            var lat = parseFloat(latStr);
            var lng = parseFloat(lngStr);
            if (isNaN(lat) || isNaN(lng)) {
                return;
            }
            var id = li.getAttribute("data-entry-id");
            var name = li.getAttribute("data-entry-name") || "Place";
            var address = li.getAttribute("data-entry-address") || "";
            var primaryTypeDisplay =
                li.getAttribute("data-primary-type-display") || "";
            var notesPrev = li.getAttribute("data-notes-preview") || "";
            var photoCount = li.getAttribute("data-photo-count") || "0";
            var thumbUrl = li.getAttribute("data-photo-thumb-url") || "";
            var tagsLabels = li.getAttribute("data-tags-labels") || "";
            var tagIdsStr = li.getAttribute("data-tag-ids") || "";
            var firstTagName = li.getAttribute("data-first-tag-name") || "";
            var firstTagBg = li.getAttribute("data-first-tag-bg") || "";
            var letterContrast =
                li.getAttribute("data-first-tag-letter-contrast") || "";
            var editUrl = li.getAttribute("data-edit-url") || "";
            var marker = L.marker([lat, lng], {
                icon: createTagMarkerIcon(
                    L,
                    firstTagBg,
                    tagIdsStr,
                    firstTagName,
                    letterContrast
                ),
            });
            var dest = encodeURIComponent(lat + "," + lng);
            var gmaps =
                "https://www.google.com/maps/dir/?api=1&amp;destination=" + dest;
            var searchQuery = [name, address].filter(Boolean).join(", ");
            var gsearch =
                "https://www.google.com/maps/search/?api=1&amp;query=" +
                encodeURIComponent(searchQuery);
            var links =
                (editUrl
                    ? '<a href="' + escapeHtml(editUrl) + '">Edit</a> · '
                    : "") +
                '<a href="' +
                gmaps +
                '" target="_blank" rel="noopener noreferrer">Directions</a> · ' +
                '<a href="' +
                gsearch +
                '" target="_blank" rel="noopener noreferrer">Open in Maps</a>';
            var metaParts = [];
            if (primaryTypeDisplay) {
                metaParts.push(escapeHtml(primaryTypeDisplay));
            }
            var nPhotos = parseInt(photoCount, 10);
            if (!isNaN(nPhotos) && nPhotos > 0) {
                metaParts.push(
                    nPhotos + " " + (nPhotos === 1 ? "photo" : "photos")
                );
            }
            var metaLine =
                metaParts.length > 0
                    ? '<div class="tlog-map-popup-meta">' +
                      metaParts.join(" · ") +
                      "</div>"
                    : "";
            var addrBlock =
                address !== ""
                    ? '<div class="tlog-map-popup-address">' +
                      escapeHtml(address) +
                      "</div>"
                    : "";
            var notesBlock =
                notesPrev !== ""
                    ? '<div class="tlog-map-popup-notes">' +
                      escapeHtml(notesPrev) +
                      "</div>"
                    : "";
            var tagsBlock =
                tagsLabels !== ""
                    ? '<div class="tlog-map-popup-tags">' +
                      escapeHtml(tagsLabels) +
                      "</div>"
                    : "";
            var thumbBlock =
                thumbUrl !== ""
                    ? '<div class="tlog-map-popup-thumb-wrap"><img src="' +
                      escapeHtml(thumbUrl) +
                      '" alt="" class="tlog-map-popup-thumb" width="240" height="135" loading="lazy"></div>'
                    : "";
            marker.bindPopup(
                '<div class="tlog-map-popup">' +
                    thumbBlock +
                    "<strong>" +
                    escapeHtml(name) +
                    "</strong>" +
                    metaLine +
                    addrBlock +
                    tagsBlock +
                    notesBlock +
                    '<div class="tlog-map-popup-links">' +
                    links +
                    "</div></div>",
                { className: "tlog-leaflet-popup", maxWidth: 300 }
            );
            markersByEntryId.set(id, marker);
        });
        syncMarkerVisibility();
    }

    function syncMarkerVisibility() {
        if (!markersLayer || !map || !window.L) {
            return;
        }
        var boundsPts = [];
        markersByEntryId.forEach(function (marker, entryId) {
            var li = document.querySelector(
                '.tlog-entry-item[data-entry-id="' + entryId + '"]'
            );
            if (!li) {
                return;
            }
            var visible = li.style.display !== "none";
            if (visible) {
                if (!markersLayer.hasLayer(marker)) {
                    markersLayer.addLayer(marker);
                }
                boundsPts.push(marker.getLatLng());
            } else if (markersLayer.hasLayer(marker)) {
                markersLayer.removeLayer(marker);
            }
        });
        if (boundsPts.length > 0) {
            map.fitBounds(L.latLngBounds(boundsPts), {
                padding: [28, 28],
                maxZoom: 15,
            });
        } else {
            map.setView([20, 0], 2);
        }
    }

    function afterMapShown() {
        if (!map) {
            return;
        }
        requestAnimationFrame(function () {
            map.invalidateSize(true);
            syncMarkerVisibility();
        });
    }

    function initMap() {
        if (mapInitialized || !mapEl || !window.L) {
            return;
        }
        mapInitialized = true;
        map = L.map(mapEl, { scrollWheelZoom: true }).setView([20, 0], 2);
        L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "",
            maxZoom: 19,
        }).addTo(map);
        markersLayer = L.featureGroup().addTo(map);
        buildMarkers();
        afterMapShown();
    }

    tabListBtn.addEventListener("click", function () {
        setView("list");
    });

    if (hasCalendarTab) {
        tabCalBtn.addEventListener("click", function () {
            setView("calendar");
        });
    }

    tabMapBtn.addEventListener("click", function () {
        setView("map");
        if (!mapEl) {
            return;
        }
        loadLeaflet()
            .then(function () {
                initMap();
                afterMapShown();
            })
            .catch(function () {
                mapEl.innerHTML =
                    "<p class=\"tlog-map-empty-message\">Could not load the map. Check your connection and try again.</p>";
            });
    });

    document.addEventListener("tlog-collection-filters-changed", function () {
        if (currentView === "map" && map) {
            syncMarkerVisibility();
        }
    });

    window.addEventListener("resize", function () {
        if (currentView === "map" && map) {
            map.invalidateSize(true);
        }
    });
})();

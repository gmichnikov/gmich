(function () {
    var boardUrl = "/election-2026/api/board";
    var pollMs = 30000;
    var data = null;
    var selected = null;
    var windowKey = "all";
    var officeKey = "all";
    var sortKey = "closest";
    var calledKey = "all";
    var viewKey = "summary";
    var mapSvgText = null;
    var mapHover = null;
    var query = "";
    var hoverState = null;
    var starred = loadStarred();
    var starStorageKey = "election2026-starred";

    var CHART = {
        width: 640,
        height: 168,
        padLeft: 36,
        padRight: 8,
        padTop: 12,
        padBottom: 22
    };
    CHART.plotWidth = CHART.width - CHART.padLeft - CHART.padRight;
    CHART.plotHeight = CHART.height - CHART.padTop - CHART.padBottom;

    var updatedEl = document.getElementById("election2026-updated");
    var errorEl = document.getElementById("election2026-error");
    var chipsEl = document.getElementById("election2026-chips");
    var gridEl = document.getElementById("election2026-grid");
    var searchEl = document.getElementById("election2026-search");
    var filtersEl = document.querySelector(".election2026-toolbar");
    var racesEl = document.querySelector(".election2026-races");
    var savedSelected = null;
    var restoringView = false;
    var viewStorageKey = "election2026-view";

    function loadStarred() {
        try {
            var parsed = JSON.parse(localStorage.getItem("election2026-starred") || "[]");
            if (!Array.isArray(parsed)) return new Set();
            return new Set(parsed.filter(function (ticker) { return typeof ticker === "string"; }));
        } catch (error) {
            return new Set();
        }
    }

    function saveStarred() {
        try {
            localStorage.setItem(starStorageKey, JSON.stringify(Array.from(starred)));
        } catch (error) {
            return;
        }
    }

    function oneOf(value, allowed, fallback) {
        return allowed.indexOf(value) === -1 ? fallback : value;
    }

    function loadViewState() {
        try {
            var parsed = JSON.parse(localStorage.getItem(viewStorageKey) || "null");
            if (!parsed || typeof parsed !== "object") return null;
            return parsed;
        } catch (error) {
            return null;
        }
    }

    function saveViewState() {
        if (restoringView) return;
        var custom = officeKey === "custom" || officeKey === "none";
        var state = {
            windowKey: windowKey,
            officeKey: officeKey,
            sortKey: sortKey,
            calledKey: calledKey,
            viewKey: viewKey,
            query: query,
            filtersOpen: filtersEl.open,
            racesOpen: racesEl.open,
            selected: custom && selected ? Array.from(selected) : null
        };
        try {
            localStorage.setItem(viewStorageKey, JSON.stringify(state));
        } catch (error) {
            return;
        }
    }

    function selectionForOffice(office, customTickers) {
        var next = new Set();
        if (!data) return next;
        if (office === "none") return next;
        if (office === "custom") {
            var keep = new Set(customTickers || []);
            data.races.forEach(function (race) {
                if (keep.has(race.event_ticker)) next.add(race.event_ticker);
            });
            return next;
        }
        data.races.forEach(function (race) {
            if (office === "all" || race.office === office || (office === "starred" && starred.has(race.event_ticker))) {
                next.add(race.event_ticker);
            }
        });
        return next;
    }

    function applySavedView() {
        var saved = loadViewState();
        if (!saved) return null;
        restoringView = true;
        windowKey = oneOf(saved.windowKey, ["all", "2h", "30m"], windowKey);
        officeKey = oneOf(saved.officeKey, ["all", "senate", "governor", "house", "starred", "none", "custom"], officeKey);
        sortKey = oneOf(saved.sortKey, ["state", "leader", "closest"], sortKey);
        calledKey = oneOf(saved.calledKey, ["all", "called", "open"], calledKey);
        viewKey = oneOf(saved.viewKey, ["lines", "bars", "map", "summary"], viewKey);
        query = typeof saved.query === "string" ? saved.query : "";
        searchEl.value = query;
        if (typeof saved.filtersOpen === "boolean") filtersEl.open = saved.filtersOpen;
        if (typeof saved.racesOpen === "boolean") racesEl.open = saved.racesOpen;
        setPressed("[data-window]", "data-window", windowKey);
        setPressed("[data-office]", "data-office", officeKey);
        setPressed("[data-sort]", "data-sort", sortKey);
        setPressed("[data-called]", "data-called", calledKey);
        setPressed("[data-view]", "data-view", viewKey);
        restoringView = false;
        return Array.isArray(saved.selected)
            ? saved.selected.filter(function (ticker) { return typeof ticker === "string"; })
            : null;
    }

    function starButton(race) {
        var on = starred.has(race.event_ticker);
        return (
            '<button type="button" class="election2026-star" data-star="' + escapeAttr(race.event_ticker) +
            '" aria-pressed="' + (on ? "true" : "false") +
            '" aria-label="' + escapeAttr((on ? "Unstar " : "Star ") + race.label) + '">' +
            (on ? "★" : "☆") +
            "</button>"
        );
    }

    function partyColor(party, index) {
        if (party === "Democrat") return "#2b6cb0";
        if (party === "Republican") return "#c53030";
        if (party === "Independent") return "#6b46c1";
        if (party === "Green") return "#2f855a";
        if (party === "Libertarian") return "#c05621";
        var fallback = ["#2f855a", "#c05621", "#4a5568"];
        return fallback[index % fallback.length];
    }

    function formatPercent(price) {
        return (price * 100).toFixed(1) + "%";
    }

    function formatDelta(points) {
        if (!points || points.length < 2) return "";
        var change = (points[points.length - 1].p - points[0].p) * 100;
        var rounded = Math.round(change * 10) / 10;
        if (rounded === 0) return "0.0";
        return (rounded > 0 ? "+" : "") + rounded.toFixed(1);
    }

    function formatClock(iso) {
        if (!iso) return "";
        return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
    }

    function normalize(value) {
        return String(value || "").toLowerCase().replace(/-/g, " ").replace(/\s+/g, " ").trim();
    }

    function stateName(race) {
        var label = race.label || "";
        var officeWord = race.office === "governor" ? "Governor" : race.office === "senate" ? "Senate" : "";
        if (officeWord && label.toLowerCase().slice(-officeWord.length) === officeWord.toLowerCase()) {
            return label.slice(0, -officeWord.length).trim();
        }
        var district = label.search(/\s+\d/);
        if (race.office === "house" && district > 0) return label.slice(0, district).trim();
        return label;
    }

    function districtNumber(race) {
        var match = /(\d+)/.exec(race.label || "");
        return match ? parseInt(match[1], 10) : 0;
    }

    function raceMatchesQuery(race) {
        var needle = normalize(query);
        if (!needle) return true;
        var fields = [stateName(race), race.state, race.label].concat((race.candidates || []).map(function (candidate) {
            return candidate.name;
        }));
        return fields.some(function (field) {
            return normalize(field).indexOf(needle) !== -1;
        });
    }

    function windowStart() {
        if (windowKey === "30m") return Date.now() - 30 * 60 * 1000;
        if (windowKey === "2h") return Date.now() - 2 * 60 * 60 * 1000;
        return null;
    }

    function pointsInWindow(points) {
        var start = windowStart();
        var kept = points.filter(function (point) {
            return start === null || new Date(point.t).getTime() >= start;
        });
        if (kept.length === 0 && points.length) {
            kept = [points[points.length - 1]];
        }
        return kept;
    }

    function leaderPrice(race) {
        var best = null;
        (race.candidates || []).forEach(function (candidate) {
            var points = candidate.points || [];
            if (!points.length) return;
            var price = points[points.length - 1].p;
            if (best === null || price > best) best = price;
        });
        return best === null ? -1 : best;
    }

    function compareRaces(a, b) {
        if (sortKey === "leader" || sortKey === "closest") {
            var priceA = leaderPrice(a);
            var priceB = leaderPrice(b);
            if ((priceA < 0) !== (priceB < 0)) return priceA < 0 ? 1 : -1;
            var byPrice = sortKey === "closest" ? priceA - priceB : priceB - priceA;
            if (byPrice !== 0) return byPrice;
        }
        var byState = stateName(a).localeCompare(stateName(b));
        if (byState !== 0) return byState;
        var byOffice = (a.office || "").localeCompare(b.office || "");
        if (byOffice !== 0) return byOffice;
        if (a.office === "house" && b.office === "house") return districtNumber(a) - districtNumber(b);
        return (a.label || "").localeCompare(b.label || "");
    }

    function orderedRaces(races) {
        return races.slice().sort(compareRaces);
    }

    function matchesCalled(race) {
        if (calledKey === "called") return !!race.called;
        if (calledKey === "open") return !race.called;
        return true;
    }

    function visibleRaces() {
        if (!data) return [];
        return orderedRaces(data.races.filter(function (race) {
            return selected.has(race.event_ticker) && raceMatchesQuery(race) && matchesCalled(race);
        }));
    }

    function sharedDomain(races) {
        var min = null;
        var max = null;
        races.forEach(function (race) {
            race.candidates.forEach(function (candidate) {
                pointsInWindow(candidate.points).forEach(function (point) {
                    var time = new Date(point.t).getTime();
                    if (min === null || time < min) min = time;
                    if (max === null || time > max) max = time;
                });
            });
        });
        return { min: min, max: max };
    }

    function xOfTime(time, domain) {
        if (domain.min === null || domain.max === null || domain.max === domain.min) {
            return CHART.padLeft + CHART.plotWidth / 2;
        }
        return CHART.padLeft + ((time - domain.min) / (domain.max - domain.min)) * CHART.plotWidth;
    }

    function chartSvg(race, domain) {
        var width = CHART.width;
        var height = CHART.height;
        var padLeft = CHART.padLeft;
        var padRight = CHART.padRight;
        var padTop = CHART.padTop;
        var plotHeight = CHART.plotHeight;
        var parts = [];

        function yOf(price) {
            var clamped = Math.max(0, Math.min(1, price));
            return padTop + (1 - clamped) * plotHeight;
        }

        parts.push('<line x1="' + padLeft + '" y1="' + yOf(0.5) + '" x2="' + (width - padRight) + '" y2="' + yOf(0.5) + '" stroke="#e4e7eb" stroke-dasharray="4 4" />');
        [0, 0.5, 1].forEach(function (price) {
            parts.push(
                '<text x="0" y="' + (yOf(price) + 4) + '" fill="#7b8794" font-size="12">' +
                Math.round(price * 100) +
                "</text>"
            );
        });

        var any = false;
        race.candidates.forEach(function (candidate, index) {
            var points = pointsInWindow(candidate.points);
            if (!points.length) return;
            any = true;
            var color = partyColor(candidate.party, index);
            if (points.length === 1) {
                parts.push(
                    '<circle cx="' + xOfTime(new Date(points[0].t).getTime(), domain) + '" cy="' + yOf(points[0].p) +
                    '" r="4" fill="' + color + '" />'
                );
                return;
            }
            var coords = points.map(function (point) {
                return xOfTime(new Date(point.t).getTime(), domain).toFixed(1) + "," + yOf(point.p).toFixed(1);
            }).join(" ");
            parts.push('<polyline fill="none" stroke="' + color + '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="' + coords + '" />');
        });

        if (domain.min !== null) {
            parts.push('<text x="' + padLeft + '" y="' + (height - 4) + '" fill="#7b8794" font-size="12">' + formatClock(new Date(domain.min).toISOString()) + "</text>");
            if (domain.max !== domain.min) {
                parts.push('<text x="' + (width - padRight) + '" y="' + (height - 4) + '" fill="#7b8794" font-size="12" text-anchor="end">' + formatClock(new Date(domain.max).toISOString()) + "</text>");
            }
        }

        if (!any) {
            return '<p class="election2026-empty">No prices yet.</p>';
        }
        return (
            '<svg class="election2026-chart" viewBox="0 0 ' + width + " " + height +
            '" role="img" aria-label="' + escapeAttr(race.label) + ' price chart">' +
            parts.join("") +
            "</svg>"
        );
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/"/g, "&quot;");
    }

    function renderUpdated() {
        if (!data || !data.last_pulled_at) {
            updatedEl.textContent = "Waiting for the first price.";
            return;
        }
        var when = formatClock(data.last_pulled_at);
        updatedEl.textContent = data.pulled
            ? "Updated " + when + ". Pulled from Kalshi just now."
            : "Updated " + when + ". Next Kalshi pull after a minute.";
    }

    function renderErrors() {
        var messages = (data && data.errors) || [];
        if (!messages.length) {
            errorEl.hidden = true;
            errorEl.textContent = "";
            return;
        }
        errorEl.hidden = false;
        errorEl.textContent = messages.join(" ");
    }

    function renderChips() {
        var races = orderedRaces(data.races.filter(function (race) {
            return raceMatchesQuery(race) && matchesCalled(race);
        }));
        if (!races.length) {
            chipsEl.innerHTML = '<p class="election2026-empty">No races match.</p>';
            return;
        }
        chipsEl.innerHTML = races.map(function (race) {
            var checked = selected.has(race.event_ticker) ? " checked" : "";
            return (
                '<span class="election2026-chip-row">' +
                starButton(race) +
                '<label class="election2026-chip">' +
                '<input type="checkbox" data-race="' + escapeAttr(race.event_ticker) + '"' + checked + ">" +
                "<span>" + escapeHtml(race.label) + "</span>" +
                "</label>" +
                "</span>"
            );
        }).join("");
    }

    function emptyBoardMessage() {
        var anyMatch = data.races.some(raceMatchesQuery);
        var starredMatch = data.races.some(function (race) {
            return starred.has(race.event_ticker) && raceMatchesQuery(race);
        });
        if (normalize(query) && !anyMatch) return "No races match.";
        var selectedMatch = data.races.some(function (race) {
            return selected.has(race.event_ticker) && raceMatchesQuery(race);
        });
        if (calledKey === "called" && selectedMatch) return "No called races.";
        if (calledKey === "open" && selectedMatch) return "No uncalled races.";
        if (officeKey === "starred" && !starredMatch) return "No starred races.";
        return "No races selected.";
    }

    function latestPoint(candidate) {
        var points = candidate.points || [];
        if (!points.length) return null;
        return points[points.length - 1].p;
    }

    function barSides(race) {
        var priced = [];
        race.candidates.forEach(function (candidate, index) {
            var price = latestPoint(candidate);
            if (price === null) return;
            priced.push({ candidate: candidate, index: index, price: price });
        });
        if (!priced.length) return null;
        priced.sort(function (a, b) { return b.price - a.price; });
        var left = null;
        var right = null;
        priced.forEach(function (row) {
            if (!left && row.candidate.party === "Democrat") left = row;
            else if (!right && row.candidate.party === "Republican") right = row;
        });
        priced.forEach(function (row) {
            if (row === left || row === right) return;
            if (!right) right = row;
            else if (!left) left = row;
        });
        return { left: left, right: right };
    }

    function renderBars() {
        hoverState = null;
        var races = visibleRaces().filter(function (race) { return barSides(race); });
        if (!races.length) {
            gridEl.innerHTML = '<p class="election2026-card election2026-empty">' + emptyBoardMessage() + "</p>";
            return;
        }
        gridEl.innerHTML = '<div class="election2026-bars">' + races.map(function (race) {
            var sides = barSides(race);
            var leftPrice = sides.left ? sides.left.price : 0;
            var rightPrice = sides.right ? sides.right.price : 0;
            var total = leftPrice + rightPrice;
            var leftPct = total ? (leftPrice / total) * 100 : 0;
            var rightPct = total ? 100 - leftPct : 0;
            function sideHtml(side, alignRight) {
                if (!side) return '<span class="election2026-split-side"></span>';
                var name = '<span class="election2026-name">' + escapeHtml(side.candidate.name) + "</span>";
                var quote = '<span class="election2026-quote">' + formatPercent(side.price) + "</span>";
                return (
                    '<span class="election2026-split-side' + (alignRight ? " election2026-split-side-right" : "") + '">' +
                    name + quote +
                    "</span>"
                );
            }
            function fillHtml(side, pct) {
                if (!side || pct <= 0) return "";
                return '<div class="election2026-split-fill" style="width:' + pct.toFixed(1) + "%;background:" + partyColor(side.candidate.party, side.index) + '"></div>';
            }
            return (
                '<div class="election2026-split">' +
                '<div class="election2026-split-title">' + escapeHtml(race.label) + "</div>" +
                '<div class="election2026-split-bar">' +
                '<div class="election2026-split-track">' + fillHtml(sides.left, leftPct) + fillHtml(sides.right, rightPct) + "</div>" +
                '<div class="election2026-split-names">' + sideHtml(sides.left, false) + sideHtml(sides.right, true) + "</div>" +
                "</div></div>"
            );
        }).join("") + "</div>";
    }

    function racesByState() {
        var groups = {};
        visibleRaces().forEach(function (race) {
            var code = (race.state || "").toUpperCase();
            if (!code) return;
            if (!groups[code]) groups[code] = [];
            groups[code].push(race);
        });
        Object.keys(groups).forEach(function (code) {
            groups[code].sort(function (a, b) {
                var byOffice = (a.office || "").localeCompare(b.office || "");
                if (byOffice !== 0) return byOffice;
                if (a.office === "house" && b.office === "house") return districtNumber(a) - districtNumber(b);
                return (a.label || "").localeCompare(b.label || "");
            });
        });
        return groups;
    }

    function mapPopupHtml(code) {
        var races = racesByState()[code] || [];
        if (!races.length) return "";
        var rows = races.map(function (race) {
            var candidates = race.candidates.map(function (candidate, index) {
                var points = candidate.points || [];
                var quote = points.length ? formatPercent(points[points.length - 1].p) : "—";
                return (
                    '<div class="election2026-map-cand">' +
                    '<span class="election2026-swatch" style="background:' + partyColor(candidate.party, index) + '"></span>' +
                    '<span class="election2026-name">' + escapeHtml(candidate.name) + "</span>" +
                    '<span class="election2026-quote">' + quote + "</span>" +
                    "</div>"
                );
            }).join("");
            return (
                '<div class="election2026-map-race">' +
                '<div class="election2026-map-race-title">' + escapeHtml(race.label) + "</div>" +
                candidates +
                "</div>"
            );
        }).join("");
        return '<div class="election2026-map-pop-title">' + escapeHtml(stateName(races[0])) + "</div>" + rows;
    }

    function hideMapPop() {
        var pop = gridEl.querySelector(".election2026-map-pop");
        if (!pop) return;
        pop.hidden = true;
        pop.innerHTML = "";
    }

    function placeMapCounts() {
        var card = gridEl.querySelector(".election2026-map-card");
        var svg = gridEl.querySelector(".election2026-map");
        if (!card || !svg) return;
        card.querySelectorAll(".election2026-map-badge").forEach(function (badge) {
            badge.remove();
        });
        var groups = racesByState();
        var cardBox = card.getBoundingClientRect();
        svg.querySelectorAll("[data-state]").forEach(function (shape) {
            var races = groups[shape.getAttribute("data-state")];
            if (!races || !races.length) return;
            var box = shape.getBoundingClientRect();
            if (box.width < 28 || box.height < 22) return;
            var badge = document.createElement("span");
            badge.className = "election2026-map-badge";
            badge.textContent = String(races.length);
            badge.style.left = (box.left - cardBox.left + box.width / 2) + "px";
            badge.style.top = (box.top - cardBox.top + box.height / 2) + "px";
            card.appendChild(badge);
        });
    }

    function showMapPop(code, clientX, clientY, pointerType) {
        var pop = gridEl.querySelector(".election2026-map-pop");
        var html = mapPopupHtml(code);
        if (!pop || !html) return;
        pop.hidden = false;
        if (!mapHover || mapHover.code !== code) pop.innerHTML = html;
        var docked = pointerType === "touch";
        pop.classList.toggle("election2026-map-pop-docked", docked);
        mapHover = { code: code, x: clientX, y: clientY, pointerType: pointerType };
        if (docked) {
            pop.style.left = "";
            pop.style.top = "";
            return;
        }
        var card = pop.parentElement;
        var rect = card.getBoundingClientRect();
        pop.style.left = (clientX - rect.left + 14) + "px";
        pop.style.top = (clientY - rect.top + 14) + "px";
        var popRect = pop.getBoundingClientRect();
        if (popRect.right > window.innerWidth - 8) {
            pop.style.left = (clientX - rect.left - popRect.width - 14) + "px";
        }
        if (popRect.bottom > window.innerHeight - 8) {
            pop.style.top = (clientY - rect.top - popRect.height - 14) + "px";
        }
    }

    function renderMap() {
        hoverState = null;
        if (!visibleRaces().length) {
            mapHover = null;
            gridEl.innerHTML = '<p class="election2026-card election2026-empty">' + emptyBoardMessage() + "</p>";
            return;
        }
        if (!mapSvgText) {
            gridEl.innerHTML = '<p class="election2026-card election2026-empty">Loading map…</p>';
            fetch(gridEl.getAttribute("data-map-url"))
                .then(function (response) {
                    if (!response.ok) throw new Error("Map request failed");
                    return response.text();
                })
                .then(function (text) {
                    mapSvgText = text;
                    if (viewKey === "map") renderMap();
                })
                .catch(function () {
                    if (viewKey === "map") {
                        gridEl.innerHTML = '<p class="election2026-card election2026-empty">The map could not be loaded.</p>';
                    }
                });
            return;
        }
        var groups = racesByState();
        gridEl.innerHTML = (
            '<div class="election2026-map-card">' +
            mapSvgText +
            '<div class="election2026-map-pop" hidden></div>' +
            "</div>"
        );
        gridEl.querySelectorAll("[data-state]").forEach(function (shape) {
            var races = groups[shape.getAttribute("data-state")];
            if (races && races.length) shape.setAttribute("data-active", "true");
        });
        placeMapCounts();
        if (mapHover && groups[mapHover.code]) showMapPop(mapHover.code, mapHover.x, mapHover.y, mapHover.pointerType);
        else mapHover = null;
    }

    function shortRace(race) {
        var state = race.state || "";
        if (race.office === "house") return state + "-" + districtNumber(race);
        if (race.office === "senate") return state + " Sen";
        if (race.office === "governor") return state + " Gov";
        return race.label || state;
    }

    function lastName(name) {
        var parts = String(name || "").trim().split(/\s+/);
        return parts[parts.length - 1] || "";
    }

    function renderSummary() {
        hoverState = null;
        var races = visibleRaces();
        if (!races.length) {
            gridEl.innerHTML = '<p class="election2026-card election2026-empty">' + emptyBoardMessage() + "</p>";
            return;
        }
        gridEl.innerHTML = '<div class="election2026-summary">' + races.map(function (race) {
            var sides = barSides(race);
            var left = sides && sides.left;
            var right = sides && sides.right;
            var leftLeads = left && (!right || left.price >= right.price);
            var rightLeads = right && (!left || right.price > left.price);
            function personHtml(side, leads) {
                if (!side) return '<span class="election2026-sum-person"></span>';
                return (
                    '<span class="election2026-sum-person' + (side === right ? " election2026-sum-person-right" : "") + '" style="color:' + partyColor(side.candidate.party, side.index) + '">' +
                    '<span class="election2026-sum-name">' + escapeHtml(lastName(side.candidate.name)) + "</span>" +
                    '<span class="election2026-sum-pct' + (leads ? " election2026-sum-pct-lead" : "") + '">' + formatPercent(side.price) + "</span>" +
                    "</span>"
                );
            }
            var detail = [race.label].concat([left, right].filter(Boolean).map(function (side) {
                return side.candidate.name + " " + formatPercent(side.price);
            })).join(", ");
            return (
                '<div class="election2026-sum" title="' + escapeAttr(detail) + '">' +
                '<span class="election2026-sum-race">' + escapeHtml(shortRace(race)) + "</span>" +
                personHtml(left, leftLeads) +
                personHtml(right, rightLeads) +
                "</div>"
            );
        }).join("") + "</div>";
    }

    function renderBoard() {
        if (viewKey === "bars") renderBars();
        else if (viewKey === "map") renderMap();
        else if (viewKey === "summary") renderSummary();
        else renderGrid();
        saveViewState();
    }

    function renderGrid() {
        var races = visibleRaces();
        if (!races.length) {
            hoverState = null;
            gridEl.innerHTML = '<p class="election2026-card election2026-empty">' + emptyBoardMessage() + "</p>";
            return;
        }
        var domain = sharedDomain(races);
        gridEl.innerHTML = races.map(function (race) {
            var candidates = race.candidates.map(function (candidate, index) {
                var points = pointsInWindow(candidate.points);
                var latest = points.length ? points[points.length - 1].p : null;
                var quote = latest === null ? "—" : formatPercent(latest);
                var delta = formatDelta(points);
                var party = candidate.party ? '<span class="election2026-party">' + escapeHtml(candidate.party) + "</span>" : "";
                var deltaHtml = delta ? ' <span class="election2026-delta">' + delta + "</span>" : "";
                return (
                    '<div class="election2026-candidate">' +
                    '<span class="election2026-swatch" style="background:' + partyColor(candidate.party, index) + '"></span>' +
                    '<span class="election2026-who"><span class="election2026-name">' + escapeHtml(candidate.name) + "</span>" + party + "</span>" +
                    '<span class="election2026-quote">' + quote + deltaHtml + "</span>" +
                    "</div>"
                );
            }).join("");
            return (
                '<article class="election2026-card">' +
                '<div class="election2026-card-top">' +
                "<div>" +
                "<h2 class=\"election2026-card-title\">" + escapeHtml(race.label) + "</h2>" +
                '<p class="election2026-office">' + escapeHtml(race.office) + "</p>" +
                "</div>" +
                starButton(race) +
                "</div>" +
                '<div class="election2026-candidates">' + candidates + "</div>" +
                chartBlock(race, domain) +
                "</article>"
            );
        }).join("");
        restoreHover();
    }

    function chartBlock(race, domain) {
        var chart = chartSvg(race, domain);
        if (chart.indexOf("<svg") !== 0) return chart;
        return (
            '<div class="election2026-chart-wrap" data-race="' + escapeAttr(race.event_ticker) + '">' +
            chart +
            '<div class="election2026-guide" hidden></div>' +
            '<div class="election2026-tip" hidden></div>' +
            "</div>"
        );
    }

    function raceByTicker(ticker) {
        if (!data) return null;
        for (var i = 0; i < data.races.length; i++) {
            if (data.races[i].event_ticker === ticker) return data.races[i];
        }
        return null;
    }

    function timeAtViewX(viewX, domain) {
        if (domain.min === null || domain.max === null) return null;
        if (domain.max === domain.min) return domain.min;
        var ratio = (viewX - CHART.padLeft) / CHART.plotWidth;
        if (ratio < 0) ratio = 0;
        if (ratio > 1) ratio = 1;
        return domain.min + ratio * (domain.max - domain.min);
    }

    function nearestTime(race, target) {
        var best = null;
        var bestDist = Infinity;
        race.candidates.forEach(function (candidate) {
            pointsInWindow(candidate.points).forEach(function (point) {
                var time = new Date(point.t).getTime();
                var dist = Math.abs(time - target);
                if (dist < bestDist) {
                    best = time;
                    bestDist = dist;
                }
            });
        });
        return best;
    }

    function pointAtTime(points, time) {
        var exact = null;
        var nearest = null;
        var bestDist = Infinity;
        points.forEach(function (point) {
            var timeValue = new Date(point.t).getTime();
            if (timeValue === time) exact = point;
            var dist = Math.abs(timeValue - time);
            if (dist < bestDist) {
                nearest = point;
                bestDist = dist;
            }
        });
        return exact || nearest;
    }

    function hideHover() {
        gridEl.querySelectorAll(".election2026-guide, .election2026-tip").forEach(function (el) {
            el.hidden = true;
        });
    }

    function showHover(wrap, clientX) {
        var race = raceByTicker(wrap.getAttribute("data-race"));
        var svg = wrap.querySelector("svg");
        if (!race || !svg) return;
        var domain = sharedDomain(visibleRaces());
        var rect = svg.getBoundingClientRect();
        if (!rect.width) return;
        var viewX = ((clientX - rect.left) / rect.width) * CHART.width;
        var target = timeAtViewX(viewX, domain);
        if (target === null) return;
        var time = nearestTime(race, target);
        if (time === null) return;
        var rows = race.candidates.map(function (candidate, index) {
            var point = pointAtTime(pointsInWindow(candidate.points), time);
            if (!point) return "";
            return (
                '<div class="election2026-tip-row">' +
                '<span class="election2026-swatch" style="background:' + partyColor(candidate.party, index) + '"></span>' +
                '<span class="election2026-tip-name">' + escapeHtml(candidate.name) + "</span>" +
                '<span class="election2026-tip-price">' + formatPercent(point.p) + "</span>" +
                "</div>"
            );
        }).join("");
        if (!rows) return;
        var guide = wrap.querySelector(".election2026-guide");
        var tip = wrap.querySelector(".election2026-tip");
        var x = xOfTime(time, domain);
        var leftPct = (x / CHART.width) * 100;
        guide.hidden = false;
        guide.style.left = leftPct + "%";
        guide.style.top = (CHART.padTop / CHART.height * 100) + "%";
        guide.style.height = (CHART.plotHeight / CHART.height * 100) + "%";
        tip.hidden = false;
        tip.innerHTML = '<div class="election2026-tip-time">' + formatClock(new Date(time).toISOString()) + "</div>" + rows;
        tip.style.top = "2px";
        tip.style.left = leftPct + "%";
        tip.style.transform = leftPct > 58 ? "translateX(calc(-100% - 8px))" : "translateX(8px)";
    }

    function restoreHover() {
        if (!hoverState) return;
        if (hoverState.pointerType === "touch") {
            var touched = gridEl.querySelector('.election2026-chart-wrap[data-race="' + CSS.escape(hoverState.ticker) + '"]');
            if (touched) showHover(touched, hoverState.clientX);
            return;
        }
        var el = document.elementFromPoint(hoverState.clientX, hoverState.clientY);
        var wrap = el && el.closest ? el.closest(".election2026-chart-wrap") : null;
        if (!wrap || !gridEl.contains(wrap)) {
            hoverState = null;
            return;
        }
        showHover(wrap, hoverState.clientX);
    }

    function trackHover(event) {
        var wrap = event.target.closest ? event.target.closest(".election2026-chart-wrap") : null;
        if (!wrap || !gridEl.contains(wrap)) {
            hideHover();
            hoverState = null;
            return;
        }
        hideHover();
        showHover(wrap, event.clientX);
        hoverState = {
            ticker: wrap.getAttribute("data-race"),
            clientX: event.clientX,
            clientY: event.clientY,
            pointerType: event.pointerType
        };
    }

    function render() {
        renderUpdated();
        renderErrors();
        renderChips();
        renderBoard();
    }

    function setPressed(selector, attr, value) {
        document.querySelectorAll(selector).forEach(function (button) {
            button.setAttribute("aria-pressed", button.getAttribute(attr) === value ? "true" : "false");
        });
    }

    function selectOffice(office) {
        officeKey = office;
        selected = selectionForOffice(office);
        setPressed("[data-office]", "data-office", office);
        render();
    }

    function resetView() {
        windowKey = "all";
        officeKey = "all";
        sortKey = "closest";
        calledKey = "all";
        viewKey = "summary";
        query = "";
        searchEl.value = "";
        filtersEl.open = true;
        racesEl.open = false;
        setPressed("[data-window]", "data-window", windowKey);
        setPressed("[data-office]", "data-office", officeKey);
        setPressed("[data-sort]", "data-sort", sortKey);
        setPressed("[data-called]", "data-called", calledKey);
        setPressed("[data-view]", "data-view", viewKey);
        if (data) {
            selected = selectionForOffice("all");
            render();
        } else {
            saveViewState();
        }
    }

    document.querySelectorAll("[data-called]").forEach(function (button) {
        button.addEventListener("click", function () {
            calledKey = button.getAttribute("data-called");
            setPressed("[data-called]", "data-called", calledKey);
            renderChips();
            renderBoard();
        });
    });

    document.querySelectorAll("[data-window]").forEach(function (button) {
        button.addEventListener("click", function () {
            windowKey = button.getAttribute("data-window");
            setPressed("[data-window]", "data-window", windowKey);
            renderBoard();
        });
    });

    document.querySelectorAll("[data-sort]").forEach(function (button) {
        button.addEventListener("click", function () {
            sortKey = button.getAttribute("data-sort");
            setPressed("[data-sort]", "data-sort", sortKey);
            renderChips();
            renderBoard();
        });
    });

    document.getElementById("election2026-reset").addEventListener("click", resetView);
    filtersEl.addEventListener("toggle", saveViewState);
    racesEl.addEventListener("toggle", saveViewState);

    document.querySelectorAll("[data-office]").forEach(function (button) {
        button.addEventListener("click", function () {
            if (!data) return;
            selectOffice(button.getAttribute("data-office"));
        });
    });

    chipsEl.addEventListener("change", function (event) {
        var input = event.target;
        if (!input || !input.getAttribute("data-race")) return;
        var ticker = input.getAttribute("data-race");
        if (input.checked) selected.add(ticker);
        else selected.delete(ticker);
        if (selected.size === 0) {
            officeKey = "none";
            setPressed("[data-office]", "data-office", "none");
        } else {
            officeKey = "custom";
            setPressed("[data-office]", "data-office", "");
        }
        renderChips();
        renderBoard();
    });

    function toggleStar(event) {
        var button = event.target.closest ? event.target.closest("[data-star]") : null;
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        var ticker = button.getAttribute("data-star");
        if (starred.has(ticker)) starred.delete(ticker);
        else starred.add(ticker);
        saveStarred();
        if (officeKey === "starred") {
            if (starred.has(ticker)) selected.add(ticker);
            else selected.delete(ticker);
        }
        renderChips();
        renderBoard();
    }

    chipsEl.addEventListener("click", toggleStar);
    gridEl.addEventListener("click", toggleStar);

    searchEl.addEventListener("input", function () {
        query = searchEl.value;
        renderChips();
        renderBoard();
    });

    document.querySelectorAll("[data-view]").forEach(function (button) {
        button.addEventListener("click", function () {
            viewKey = button.getAttribute("data-view");
            setPressed("[data-view]", "data-view", viewKey);
            renderBoard();
        });
    });

    function activeMapState(event) {
        if (event.target.closest && event.target.closest(".election2026-map-pop")) return null;
        var shape = event.target.closest ? event.target.closest("[data-active='true']") : null;
        return shape;
    }

    gridEl.addEventListener("pointermove", function (event) {
        if (event.pointerType === "touch") return;
        if (viewKey === "map") {
            var shape = activeMapState(event);
            if (!shape) {
                hideMapPop();
                mapHover = null;
                return;
            }
            showMapPop(shape.getAttribute("data-state"), event.clientX, event.clientY, "mouse");
            return;
        }
        trackHover(event);
    });

    gridEl.addEventListener("pointerdown", function (event) {
        if (event.pointerType !== "touch") return;
        if (viewKey === "map") {
            var shape = activeMapState(event);
            if (!shape) {
                hideMapPop();
                mapHover = null;
                return;
            }
            var code = shape.getAttribute("data-state");
            if (mapHover && mapHover.code === code && mapHover.pointerType === "touch") {
                hideMapPop();
                mapHover = null;
                return;
            }
            showMapPop(code, event.clientX, event.clientY, "touch");
            return;
        }
        trackHover(event);
    });

    gridEl.addEventListener("pointerleave", function (event) {
        if (event.pointerType === "touch") return;
        hideHover();
        hoverState = null;
        if (viewKey === "map" && (!mapHover || mapHover.pointerType !== "touch")) {
            hideMapPop();
            mapHover = null;
        }
    });

    window.addEventListener("resize", function () {
        if (viewKey === "map") placeMapCounts();
    });

    gridEl.addEventListener("pointercancel", function () {
        hideHover();
        hoverState = null;
    });

    function applyPayload(payload) {
        var first = selected === null;
        data = payload;
        if (first) {
            selected = selectionForOffice(officeKey, savedSelected);
        } else {
            var known = new Set(payload.races.map(function (race) { return race.event_ticker; }));
            payload.races.forEach(function (race) {
                if (!selected.has(race.event_ticker) && officeKey === "all") {
                    selected.add(race.event_ticker);
                }
            });
            Array.from(selected).forEach(function (ticker) {
                if (!known.has(ticker)) selected.delete(ticker);
            });
        }
        render();
    }

    function load() {
        fetch(boardUrl)
            .then(function (response) {
                if (!response.ok) throw new Error("Board request failed");
                return response.json();
            })
            .then(applyPayload)
            .catch(function () {
                updatedEl.textContent = "Could not load prices.";
            });
    }

    savedSelected = applySavedView();
    load();
    setInterval(load, pollMs);
})();

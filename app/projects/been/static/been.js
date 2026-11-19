(function () {
    const input = document.getElementById("been-search");
    const results = document.getElementById("been-results");
    const form = document.getElementById("been-pick-form");
    const title = document.getElementById("been-pick-title");
    const meta = document.getElementById("been-pick-meta");

    if (input && results && form && title && meta) {
        let timer = null;
        let controller = null;
        const fields = [
            "name",
            "kind",
            "lat",
            "lng",
            "country_code",
            "country_name",
            "region_name",
            "city",
            "osm_type",
            "osm_id",
            "osm_key",
            "osm_value",
        ];

        function clearResults() {
            results.replaceChildren();
            results.hidden = true;
        }

        function showMessage(message) {
            results.replaceChildren();
            const note = document.createElement("p");
            note.className = "been-results-message";
            note.textContent = message;
            results.appendChild(note);
            results.hidden = false;
        }

        function selectPlace(place) {
            fields.forEach(function (key) {
                const field = form.elements[key];
                if (field) {
                    field.value = place[key] == null ? "" : place[key];
                }
            });
            title.textContent = place.name || "";
            meta.textContent = place.subtitle || "";
            form.hidden = false;
            clearResults();
            input.value = place.name || "";
            if (form.elements.when) {
                form.elements.when.focus();
            }
        }

        function render(items) {
            results.replaceChildren();
            if (!items.length) {
                showMessage("No matches.");
                return;
            }
            items.forEach(function (place) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "been-result";
                const name = document.createElement("span");
                name.className = "been-result-name";
                name.textContent = place.name || "";
                button.appendChild(name);
                if (place.subtitle) {
                    const sub = document.createElement("span");
                    sub.className = "been-result-sub";
                    sub.textContent = place.subtitle;
                    button.appendChild(sub);
                }
                button.addEventListener("click", function () {
                    selectPlace(place);
                });
                results.appendChild(button);
            });
            results.hidden = false;
        }

        input.addEventListener("input", function () {
            form.hidden = true;
            const query = input.value.trim();
            if (timer) {
                clearTimeout(timer);
            }
            if (query.length < 2) {
                clearResults();
                return;
            }
            timer = setTimeout(async function () {
                if (controller) {
                    controller.abort();
                }
                controller = new AbortController();
                try {
                    const response = await fetch(
                        input.dataset.searchUrl + "?q=" + encodeURIComponent(query),
                        {
                            signal: controller.signal,
                            headers: { Accept: "application/json" },
                        }
                    );
                    const data = await response.json();
                    if (!response.ok) {
                        showMessage(data.error || "Place search is unavailable right now.");
                        return;
                    }
                    render(data.results || []);
                } catch (err) {
                    if (err.name !== "AbortError") {
                        showMessage("Place search is unavailable right now.");
                    }
                }
            }, 250);
        });

        const clearButton = document.getElementById("been-pick-clear");
        if (clearButton) {
            clearButton.addEventListener("click", function () {
                form.hidden = true;
                form.reset();
                input.focus();
            });
        }
    }

    document.querySelectorAll("form.been-wait").forEach(function (waitForm) {
        let sent = false;
        waitForm.addEventListener("submit", function (event) {
            if (sent) {
                event.preventDefault();
                return;
            }
            sent = true;
            const button = waitForm.querySelector("[type=submit]");
            if (button && button.dataset.loading) {
                button.textContent = button.dataset.loading;
            }
        });
    });
})();

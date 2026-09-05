(function () {
    "use strict";

    var searchInput = document.getElementById("cnoAdminSearch");
    var confusingOnlyInput = document.getElementById("cnoAdminConfusingOnly");
    var statusEl = document.getElementById("cnoAdminStatus");
    var listEl = document.getElementById("cnoAdminList");
    var allWords = [];

    function renderList() {
        var query = searchInput.value.trim().toUpperCase();
        var confusingOnly = confusingOnlyInput.checked;
        var filtered = allWords.filter(function (entry) {
            if (confusingOnly && !entry.confusing) {
                return false;
            }
            if (query && entry.word.indexOf(query) === -1) {
                return false;
            }
            return true;
        });

        statusEl.textContent = filtered.length + " word(s)";
        listEl.innerHTML = "";

        filtered.forEach(function (entry) {
            var row = document.createElement("label");
            row.className = "cno-admin-row";

            var checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.checked = entry.confusing;
            checkbox.addEventListener("change", function () {
                fetch("/codenames-online/admin/confusing-words", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": CNO_CSRF_TOKEN,
                    },
                    credentials: "same-origin",
                    body: JSON.stringify({
                        word: entry.word,
                        confusing: checkbox.checked,
                    }),
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok) {
                                throw new Error(data.error || "Save failed.");
                            }
                            entry.confusing = checkbox.checked;
                        });
                    })
                    .catch(function (err) {
                        checkbox.checked = !checkbox.checked;
                        statusEl.textContent = err.message;
                    });
            });

            var text = document.createElement("span");
            text.className = "cno-admin-word";
            text.textContent = entry.word;

            var meta = document.createElement("span");
            meta.className = "cno-admin-meta";
            meta.textContent = entry.lists.join(", ");

            row.appendChild(checkbox);
            row.appendChild(text);
            row.appendChild(meta);
            listEl.appendChild(row);
        });
    }

    fetch("/codenames-online/admin/confusing-words/data", { credentials: "same-origin" })
        .then(function (response) {
            return response.json();
        })
        .then(function (data) {
            allWords = data.words || [];
            renderList();
        })
        .catch(function () {
            statusEl.textContent = "Could not load words.";
        });

    searchInput.addEventListener("input", renderList);
    confusingOnlyInput.addEventListener("change", renderList);
})();

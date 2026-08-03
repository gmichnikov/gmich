/**
 * speaker — AAC word board with phrase library and speech synthesis.
 */
(function () {
    "use strict";

    var STORAGE_FAVORITES = "speaker_favorite_phrase_ids";
    var STORAGE_VOLUME = "speaker_volume";
    var STORAGE_SPEAK_MODE = "speaker_speak_mode";
    var STORAGE_COMMON_WORDS = "speaker_common_words_v1";
    var STORAGE_SHOW_FAVORITES = "speaker_show_favorites_strip";

    var PHRASE_GROUPS = [
        {
            category: "Mobility & positioning",
            phrases: [
                "Please move me to the table",
                "Please move me to the couch",
                "Please take me to the bathroom",
                "I want to sit up",
                "I want to lie down",
                "Help me walk",
                "Please push my wheelchair",
                "I want to get in bed",
                "I want to get out of bed",
                "I need to go to the toilet",
                "Bring the wheelchair",
                "Bring the walker",
                "Bring me to the table",
                "I want to go to bed",
                "I want to nap",
            ],
        },
        {
            category: "Temperature & clothing",
            phrases: [
                "I am cold",
                "I am warm",
                "Please give me a jacket",
                "Please give me a sweater",
                "This is too hot",
                "This is too cold",
                "I need my sweater",
                "I need my socks",
                "Help me get dressed",
                "Help me undress",
                "I want a blanket",
                "I want another blanket",
                "My skin feels dry",
                "My hands are cold",
                "My feet are cold",
            ],
        },
        {
            category: "Food & drink",
            phrases: [
                "I want coffee",
                "I want tea",
                "I want juice",
                "I am full",
                "I don't want to eat",
                "My mouth is dry",
                "I need a straw",
                "I am done",
                "I am hungry",
                "I am thirsty",
                "Please give me more",
            ],
        },
        {
            category: "Health & body",
            phrases: [
                "Is it time for my medicine?",
                "I need my glasses",
                "I need my hearing aids",
                "I feel dizzy",
                "I feel nauseous",
                "I feel weak",
                "It hurts here",
                "My head hurts",
                "My skin itches",
                "My stomach hurts",
                "The pain is better",
                "The pain is worse",
                "I need a heating pad",
                "I'm wet",
                "I need a tissue",
            ],
        },
        {
            category: "Home & devices",
            phrases: [
                "Turn up the volume",
                "Turn down the volume",
                "Open the window",
                "Close the window",
                "Open the curtains",
                "Close the curtains",
                "It's too loud",
                "It's too quiet",
                "I want music",
                "Change the channel",
                "I want to use the phone",
                "I want to use the tablet",
                "I want to call Greg",
                "My device needs charging",
                "Close the door",
                "Open the door",
                "Turn off the fan",
                "Turn on the fan",
            ],
        },
        {
            category: "Communication",
            phrases: [
                "Write it down for me",
                "I don't understand",
                "Please repeat that",
                "Please speak slower",
                "I don't remember",
                "Remind me later",
                "Tell me again",
                "Please say it again",
            ],
        },
        {
            category: "Feelings & social",
            phrases: [
                "I'm sorry",
                "Never mind",
                "I changed my mind",
                "Let's try again",
                "What did you do in school today?",
            ],
        },
        {
            category: "Activities & outings",
            phrases: [
                "I want to go to the game",
                "I don't want to go to the game",
                "I want to change my clothes",
                "I want a shower",
                "I want a bath",
                "I want to read",
                "I want some fresh air",
                "I want to sit in the sun",
                "I want shade",
            ],
        },
        {
            category: "Weather & time",
            phrases: [
                "What time is it?",
                "When is my appointment?",
                "Is it raining?",
                "Is it sunny?",
                "What is the temperature?",
                "What is the weather today?",
            ],
        },
    ];

    var COMMON_PHRASES = [];
    PHRASE_GROUPS.forEach(function (group, gi) {
        group.phrases.forEach(function (text, i) {
            COMMON_PHRASES.push({
                id: "p" + gi + "-" + i,
                text: text,
                category: group.category,
            });
        });
    });

    function stripPunct(w) {
        return w.replace(/[?,.!]+$/, "");
    }

    var PHRASES = COMMON_PHRASES.map(function (p) {
        return p.text.split(" ").map(stripPunct);
    });

    var DEFAULT_FAVORITE_TEXTS = [
        "Please take me to the bathroom",
        "I am cold",
        "I want coffee",
        "It hurts here",
        "I don't understand",
        "What time is it?",
    ];

    var DEFAULT_FAVORITES = COMMON_PHRASES.filter(function (p) {
        return DEFAULT_FAVORITE_TEXTS.indexOf(p.text) !== -1;
    }).map(function (p) {
        return p.id;
    });

    var CORE_WORDS = [
        "A", "Again", "Am", "Bathroom",
        "Bring", "Cold", "Don't", "Done",
        "Feel", "Give", "Go", "Help",
        "I", "Is", "It", "Me",
        "More", "My", "Need", "No",
        "Please", "Thank you", "That", "The",
        "To", "Too", "Turn", "Wait",
        "Want", "What", "Yes", "You",
    ].sort(function (a, b) {
        return a.localeCompare(b);
    });

    var state = {
        sentence: [],
        volume: 0.85,
        speakMode: "submit",
        letterBuffer: "",
        favorites: DEFAULT_FAVORITES.slice(),
        favoritesLoaded: false,
        showFavoritesStrip: false,
    };

    var SPELL_SUGGESTION_LIMIT = 6;
    var commonWords = [];
    var commonWordMatchKeys = [];
    var commonWordsLoadPromise = null;

    var els = {};

    function normalizeMatchKey(text) {
        return text.toLowerCase().replace(/[''`´]/g, "").replace(/\./g, "");
    }

    function getCurrentWordPrefix() {
        var lastSpace = state.letterBuffer.lastIndexOf(" ");
        return state.letterBuffer.slice(lastSpace + 1);
    }

    function buildSpellSuggestions() {
        var prefix = getCurrentWordPrefix();
        if (prefix.length < 1 || commonWords.length === 0) {
            return [];
        }

        var prefixKey = normalizeMatchKey(prefix);
        var results = [];

        for (var i = 0; i < commonWords.length; i++) {
            if (commonWordMatchKeys[i].indexOf(prefixKey) === 0) {
                results.push(commonWords[i]);
                if (results.length >= SPELL_SUGGESTION_LIMIT) {
                    break;
                }
            }
        }

        return results;
    }

    function ensureCommonWordsLoaded() {
        if (commonWordsLoadPromise) {
            return commonWordsLoadPromise;
        }

        var cached = loadStorage(STORAGE_COMMON_WORDS, null);
        if (Array.isArray(cached) && cached.length > 0) {
            commonWords = cached;
            commonWordMatchKeys = cached.map(normalizeMatchKey);
            commonWordsLoadPromise = Promise.resolve();
            return commonWordsLoadPromise;
        }

        var url = window.SPEAKER_COMMON_WORDS_URL;
        if (!url) {
            commonWordsLoadPromise = Promise.resolve();
            return commonWordsLoadPromise;
        }

        commonWordsLoadPromise = fetch(url)
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("Failed to load common words");
                }
                return response.json();
            })
            .then(function (words) {
                if (!Array.isArray(words)) {
                    return;
                }
                commonWords = words;
                commonWordMatchKeys = words.map(normalizeMatchKey);
                saveStorage(STORAGE_COMMON_WORDS, words);
            })
            .catch(function () {
                commonWords = [];
                commonWordMatchKeys = [];
            });

        return commonWordsLoadPromise;
    }

    function applySpellSuggestion(word) {
        state.letterBuffer = "";
        addWord(word);
        renderLetterBuffer();
    }

    function renderSpellSuggestions() {
        if (!els.spellSuggestions || !els.spellSuggestionsList) {
            return;
        }

        var suggestions = buildSpellSuggestions();
        var list = els.spellSuggestionsList;
        list.innerHTML = "";

        if (suggestions.length === 0) {
            els.spellSuggestions.classList.add("speaker-hidden");
            return;
        }

        els.spellSuggestions.classList.remove("speaker-hidden");
        suggestions.forEach(function (word) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "speaker-chip speaker-chip--spell";
            btn.textContent = word;
            btn.addEventListener("click", function () {
                applySpellSuggestion(word);
            });
            list.appendChild(btn);
        });
    }

    function $(id) {
        return document.getElementById(id);
    }

    var PLEASE_WORD = "please";

    function wordsMatchPrefix(pLower, pStart, sentenceLower, sStart) {
        var si = sStart;
        var pi = pStart;
        while (si < sentenceLower.length) {
            if (pi >= pLower.length) {
                return false;
            }
            if (pLower[pi] !== sentenceLower[si]) {
                return false;
            }
            pi += 1;
            si += 1;
        }
        return true;
    }

    /** Next-word candidates for one phrase; please is optional on either side. */
    function nextWordsForPhrase(phrase, sentenceLower) {
        var pLower = phrase.map(function (w) {
            return w.toLowerCase();
        });
        var phraseHasPlease = pLower.length > 0 && pLower[0] === PLEASE_WORD;
        var sentenceHasPlease = sentenceLower.length > 0 && sentenceLower[0] === PLEASE_WORD;
        var candidates = [];

        function tryMatch(pStart, sStart) {
            if (!wordsMatchPrefix(pLower, pStart, sentenceLower, sStart)) {
                return;
            }
            var nextIndex = pStart + (sentenceLower.length - sStart);
            if (nextIndex < phrase.length) {
                candidates.push(phrase[nextIndex]);
            }
        }

        tryMatch(0, 0);

        if (phraseHasPlease) {
            tryMatch(1, 0);
        }

        if (sentenceHasPlease && !phraseHasPlease) {
            tryMatch(0, 1);
        }

        return candidates;
    }

    function buildPredictions(sentence) {
        var lower = sentence.map(function (w) {
            return w.toLowerCase();
        });
        var counts = new Map();

        PHRASES.forEach(function (phrase) {
            var seenForPhrase = {};
            nextWordsForPhrase(phrase, lower).forEach(function (word) {
                if (seenForPhrase[word]) {
                    return;
                }
                seenForPhrase[word] = true;
                counts.set(word, (counts.get(word) || 0) + 1);
            });
        });

        return Array.from(counts.entries())
            .sort(function (a, b) {
                return b[1] - a[1];
            })
            .map(function (entry) {
                return entry[0];
            })
            .slice(0, 6);
    }

    function speak(text) {
        if (!window.speechSynthesis) {
            return;
        }
        window.speechSynthesis.cancel();
        var utter = new SpeechSynthesisUtterance(text);
        utter.volume = state.volume;
        utter.rate = 0.95;
        window.speechSynthesis.speak(utter);
    }

    function addWord(word) {
        state.sentence.push(word);
        if (state.speakMode === "immediate") {
            speak(word);
        }
        render();
    }

    function speakSentence() {
        if (state.sentence.length === 0) {
            return;
        }
        speak(state.sentence.join(" "));
    }

    function usePhrase(text) {
        state.sentence = text.split(" ");
        closeModal("phrases");
        if (state.speakMode === "immediate") {
            speak(text);
        }
        render();
    }

    function toggleFavorite(id) {
        var idx = state.favorites.indexOf(id);
        if (idx === -1) {
            state.favorites.push(id);
        } else {
            state.favorites.splice(idx, 1);
        }
        persistFavorites();
        renderFavoritesStrip();
        renderPhrasesModal();
    }

    function backspace() {
        state.sentence.pop();
        render();
    }

    function clearAll() {
        state.sentence = [];
        render();
    }

    function addLetter(letter) {
        state.letterBuffer += letter;
        renderLetterBuffer();
    }

    function backspaceLetter() {
        state.letterBuffer = state.letterBuffer.slice(0, -1);
        renderLetterBuffer();
    }

    function commitSpelledWord() {
        var word = state.letterBuffer.trim();
        if (word.length > 0) {
            addWord(word);
        }
        state.letterBuffer = "";
        renderLetterBuffer();
    }

    function loadStorage(key, fallback) {
        try {
            var raw = localStorage.getItem(key);
            if (raw === null) {
                return fallback;
            }
            return JSON.parse(raw);
        } catch (err) {
            return fallback;
        }
    }

    function saveStorage(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
        } catch (err) {
            /* ignore */
        }
    }

    function persistFavorites() {
        if (!state.favoritesLoaded) {
            return;
        }
        saveStorage(STORAGE_FAVORITES, state.favorites);
    }

    function updateBodyScrollLock() {
        var names = ["keyboard", "phrases", "settings"];
        var anyOpen = names.some(function (name) {
            var modal = $("speaker-modal-" + name);
            return modal && !modal.classList.contains("speaker-hidden");
        });
        document.body.classList.toggle("speaker-body-locked", anyOpen);
    }

    function openModal(name) {
        var modal = $("speaker-modal-" + name);
        if (modal) {
            modal.classList.remove("speaker-hidden");
        }
        updateBodyScrollLock();
    }

    function closeModal(name) {
        var modal = $("speaker-modal-" + name);
        if (modal) {
            modal.classList.add("speaker-hidden");
        }
        updateBodyScrollLock();
    }

    function renderSentence() {
        var container = els.sentenceDisplay;
        container.innerHTML = "";

        if (state.sentence.length === 0) {
            var placeholder = document.createElement("span");
            placeholder.className = "speaker-sentence-placeholder";
            placeholder.textContent = "Tap words to build a sentence...";
            container.appendChild(placeholder);
        } else {
            state.sentence.forEach(function (word) {
                var span = document.createElement("span");
                span.className = "speaker-sentence-word";
                span.textContent = word;
                container.appendChild(span);
            });
        }

        els.speakBtn.disabled = state.sentence.length === 0;
    }

    function renderPredictions() {
        var predictions = buildPredictions(state.sentence);
        var list = els.predictionsList;
        list.innerHTML = "";

        if (predictions.length === 0) {
            els.predictionsEmpty.classList.remove("speaker-hidden");
            els.predictionsFilled.classList.add("speaker-hidden");
            return;
        }

        els.predictionsEmpty.classList.add("speaker-hidden");
        els.predictionsFilled.classList.remove("speaker-hidden");

        predictions.forEach(function (word) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "speaker-chip speaker-chip--prediction";
            btn.textContent = word;
            btn.addEventListener("click", function () {
                addWord(word);
            });
            list.appendChild(btn);
        });
    }

    function renderFavoritesStrip() {
        var favoritePhrases = COMMON_PHRASES.filter(function (p) {
            return state.favorites.indexOf(p.id) !== -1;
        });
        var list = els.favoritesList;
        list.innerHTML = "";

        if (favoritePhrases.length === 0 || !state.showFavoritesStrip) {
            els.favoritesSection.classList.add("speaker-hidden");
            return;
        }

        els.favoritesSection.classList.remove("speaker-hidden");
        favoritePhrases.forEach(function (p) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "speaker-chip speaker-chip--favorite";
            btn.textContent = p.text;
            btn.addEventListener("click", function () {
                usePhrase(p.text);
            });
            list.appendChild(btn);
        });
    }

    function renderLetterBuffer() {
        var trimmed = state.letterBuffer.trim();
        els.addWordBtn.disabled = trimmed.length === 0;

        if (state.letterBuffer.length === 0) {
            els.letterBuffer.textContent = "...";
            els.letterBuffer.classList.add("speaker-spell-buffer--empty");
        } else {
            els.letterBuffer.textContent = state.letterBuffer;
            els.letterBuffer.classList.remove("speaker-spell-buffer--empty");
        }

        renderSpellSuggestions();
    }

    function renderSpeakMode() {
        var immediate = state.speakMode === "immediate";
        els.modeImmediate.classList.toggle("speaker-mode-btn--active", immediate);
        els.modeSubmit.classList.toggle("speaker-mode-btn--active", !immediate);
    }

    function renderFavoritesStripSetting() {
        els.favoritesShow.classList.toggle("speaker-mode-btn--active", state.showFavoritesStrip);
        els.favoritesHide.classList.toggle("speaker-mode-btn--active", !state.showFavoritesStrip);
    }

    function renderPhrasesModal() {
        var body = els.phrasesBody;
        body.innerHTML = "";

        PHRASE_GROUPS.forEach(function (group) {
            var section = document.createElement("div");
            section.className = "speaker-phrase-category";

            var title = document.createElement("div");
            title.className = "speaker-phrase-category-title";
            title.textContent = group.category.toUpperCase();
            section.appendChild(title);

            var list = document.createElement("div");
            list.className = "speaker-phrase-list";

            COMMON_PHRASES.filter(function (p) {
                return p.category === group.category;
            }).forEach(function (p) {
                var isFav = state.favorites.indexOf(p.id) !== -1;
                var row = document.createElement("div");
                row.className = "speaker-phrase-row";

                var textBtn = document.createElement("button");
                textBtn.type = "button";
                textBtn.className = "speaker-phrase-text-btn";
                textBtn.textContent = p.text;
                textBtn.addEventListener("click", function () {
                    usePhrase(p.text);
                });

                var starBtn = document.createElement("button");
                starBtn.type = "button";
                starBtn.className = "speaker-phrase-star-btn" + (isFav ? " speaker-phrase-star-btn--active" : "");
                starBtn.setAttribute("aria-label", isFav ? "Remove from quick access" : "Add to quick access");
                starBtn.innerHTML =
                    '<svg class="speaker-star-icon" viewBox="0 0 24 24" aria-hidden="true">' +
                    '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>' +
                    "</svg>";
                starBtn.addEventListener("click", function () {
                    toggleFavorite(p.id);
                });

                row.appendChild(textBtn);
                row.appendChild(starBtn);
                list.appendChild(row);
            });

            section.appendChild(list);
            body.appendChild(section);
        });
    }

    function render() {
        renderSentence();
        renderPredictions();
        renderFavoritesStrip();
    }

    function buildCoreGrid() {
        var grid = els.coreGrid;
        CORE_WORDS.forEach(function (word) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "speaker-word-btn";
            btn.textContent = word;
            btn.addEventListener("click", function () {
                addWord(word);
            });
            grid.appendChild(btn);
        });
    }

    function buildLetterGrid() {
        var grid = els.letterGrid;
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").forEach(function (letter) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "speaker-letter-btn";
            btn.textContent = letter;
            btn.addEventListener("click", function () {
                addLetter(letter);
            });
            grid.appendChild(btn);
        });
    }

    function bindEvents() {
        els.btnPhrases.addEventListener("click", function () {
            openModal("phrases");
        });
        els.btnKeyboard.addEventListener("click", function () {
            state.letterBuffer = "";
            renderLetterBuffer();
            openModal("keyboard");
            ensureCommonWordsLoaded().then(function () {
                renderSpellSuggestions();
            });
        });
        els.btnSettings.addEventListener("click", function () {
            openModal("settings");
        });
        els.speakBtn.addEventListener("click", speakSentence);
        els.btnBackspace.addEventListener("click", backspace);
        els.btnClear.addEventListener("click", clearAll);
        els.btnLetterSpace.addEventListener("click", function () {
            addLetter(" ");
        });
        els.btnLetterBackspace.addEventListener("click", backspaceLetter);
        els.addWordBtn.addEventListener("click", commitSpelledWord);

        els.volumeInput.addEventListener("input", function () {
            state.volume = parseFloat(els.volumeInput.value);
            saveStorage(STORAGE_VOLUME, state.volume);
        });

        els.modeImmediate.addEventListener("click", function () {
            state.speakMode = "immediate";
            renderSpeakMode();
            saveStorage(STORAGE_SPEAK_MODE, state.speakMode);
        });
        els.modeSubmit.addEventListener("click", function () {
            state.speakMode = "submit";
            renderSpeakMode();
            saveStorage(STORAGE_SPEAK_MODE, state.speakMode);
        });

        els.favoritesShow.addEventListener("click", function () {
            state.showFavoritesStrip = true;
            renderFavoritesStripSetting();
            renderFavoritesStrip();
            saveStorage(STORAGE_SHOW_FAVORITES, state.showFavoritesStrip);
        });
        els.favoritesHide.addEventListener("click", function () {
            state.showFavoritesStrip = false;
            renderFavoritesStripSetting();
            renderFavoritesStrip();
            saveStorage(STORAGE_SHOW_FAVORITES, state.showFavoritesStrip);
        });

        document.querySelectorAll("[data-speaker-close]").forEach(function (el) {
            el.addEventListener("click", function () {
                closeModal(el.getAttribute("data-speaker-close"));
            });
        });

        if (window.speechSynthesis) {
            window.speechSynthesis.onvoiceschanged = function () {
                window.speechSynthesis.getVoices();
            };
            window.speechSynthesis.getVoices();
        }
    }

    function loadSettings() {
        var savedFavorites = loadStorage(STORAGE_FAVORITES, null);
        if (Array.isArray(savedFavorites)) {
            state.favorites = savedFavorites;
        }

        var savedVolume = loadStorage(STORAGE_VOLUME, null);
        if (typeof savedVolume === "number") {
            state.volume = savedVolume;
            els.volumeInput.value = String(savedVolume);
        }

        var savedMode = loadStorage(STORAGE_SPEAK_MODE, null);
        if (savedMode === "immediate" || savedMode === "submit") {
            state.speakMode = savedMode;
        }

        var savedShowFavorites = loadStorage(STORAGE_SHOW_FAVORITES, null);
        if (typeof savedShowFavorites === "boolean") {
            state.showFavoritesStrip = savedShowFavorites;
        }

        state.favoritesLoaded = true;
        renderSpeakMode();
        renderFavoritesStripSetting();
    }

    function init() {
        els = {
            sentenceDisplay: $("speaker-sentence-display"),
            speakBtn: $("speaker-btn-speak"),
            btnPhrases: $("speaker-btn-phrases"),
            btnKeyboard: $("speaker-btn-keyboard"),
            btnSettings: $("speaker-btn-settings"),
            btnBackspace: $("speaker-btn-backspace"),
            btnClear: $("speaker-btn-clear"),
            predictionsEmpty: $("speaker-predictions-empty"),
            predictionsFilled: $("speaker-predictions-filled"),
            predictionsList: $("speaker-predictions-list"),
            favoritesSection: $("speaker-favorites"),
            favoritesList: $("speaker-favorites-list"),
            coreGrid: $("speaker-core-grid"),
            letterBuffer: $("speaker-letter-buffer"),
            spellSuggestions: $("speaker-spell-suggestions"),
            spellSuggestionsList: $("speaker-spell-suggestions-list"),
            letterGrid: $("speaker-letter-grid"),
            btnLetterSpace: $("speaker-btn-letter-space"),
            btnLetterBackspace: $("speaker-btn-letter-backspace"),
            addWordBtn: $("speaker-btn-add-word"),
            phrasesBody: $("speaker-phrases-body"),
            volumeInput: $("speaker-volume"),
            modeImmediate: $("speaker-mode-immediate"),
            modeSubmit: $("speaker-mode-submit"),
            favoritesShow: $("speaker-favorites-show"),
            favoritesHide: $("speaker-favorites-hide"),
        };

        loadSettings();
        buildCoreGrid();
        buildLetterGrid();
        renderPhrasesModal();
        renderLetterBuffer();
        render();
        bindEvents();
        updateBodyScrollLock();
        ensureCommonWordsLoaded();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());

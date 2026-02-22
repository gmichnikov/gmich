/**
 * Kids Words - vanilla JS game logic
 * All letters displayed uppercase; word lists stay lowercase for validation
 */

(function () {
  "use strict";

  const API = window.KIDS_WORDS_API || {};
  let validGuesses = new Set();
  let answerSets = { grade2: [], grade4: [], adult: [] };
  let dataReady = false;
  let selectedDifficulty = null;
  let selectedWordCount = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function all(sel, root) {
    return (root || document).querySelectorAll(sel);
  }

  function loadData() {
    const loadingEl = byId("kwLoading");
    const setupContentEl = byId("kwSetupContent");

    loadingEl.classList.remove("kw-hidden");
    setupContentEl.classList.add("kw-hidden");

    Promise.all([
      fetch(API.grade2).then((r) => r.json()),
      fetch(API.grade4).then((r) => r.json()),
      fetch(API.guesses).then((r) => r.json()),
    ])
      .then(function ([grade2Data, grade4Data, guessesArr]) {
        validGuesses = new Set(
          Object.keys(grade2Data).concat(
            Object.keys(grade4Data),
            guessesArr.filter(Boolean)
          )
        );

        answerSets.grade2 = Object.keys(grade2Data).filter(
          (w) => grade2Data[w] === "yes"
        );
        answerSets.grade4 = Object.keys(grade4Data).filter(
          (w) => grade4Data[w] === "yes"
        );
        answerSets.adult = Object.keys(grade2Data);

        dataReady = true;
        loadingEl.classList.add("kw-hidden");
        setupContentEl.classList.remove("kw-hidden");
        updateStartButton();
      })
      .catch(function (err) {
        console.error("Kids Words: failed to load data", err);
        if (loadingEl) loadingEl.textContent = "Failed to load word lists. Please refresh.";
      });
  }

  function updateStartButton() {
    const btn = byId("kwStartBtn");
    if (!btn) return;
    btn.disabled = !dataReady || !selectedDifficulty || !selectedWordCount;
  }

  function selectDifficulty(difficulty) {
    selectedDifficulty = difficulty || null;
    all(".kw-difficulty-btn").forEach(function (b) {
      b.classList.toggle("kw-selected", b.dataset.difficulty === selectedDifficulty);
    });
    updateStartButton();
  }

  function selectWordCount(count) {
    selectedWordCount = count === undefined || count === null ? null : parseInt(count, 10);
    all(".kw-word-count-btn").forEach(function (b) {
      b.classList.toggle(
        "kw-selected",
        parseInt(b.dataset.count, 10) === selectedWordCount
      );
    });
    updateStartButton();
  }

  function pickRandomAnswers(count) {
    const arr = answerSets[selectedDifficulty];
    if (!arr || arr.length < count) return [];
    const shuffled = arr.slice().sort(function () { return Math.random() - 0.5; });
    const seen = new Set();
    const out = [];
    for (let i = 0; i < shuffled.length && out.length < count; i++) {
      if (!seen.has(shuffled[i])) {
        seen.add(shuffled[i]);
        out.push(shuffled[i]);
      }
    }
    return out;
  }

  function startGame() {
    if (!selectedDifficulty || !selectedWordCount) return;
    const answers = pickRandomAnswers(selectedWordCount);
    if (answers.length !== selectedWordCount) return;

    byId("kwSetup").classList.add("kw-hidden");
    byId("kwGame").classList.remove("kw-hidden");

    const board = byId("kwBoard");
    board.innerHTML = "";
    const msg = document.createElement("p");
    msg.className = "kw-board-placeholder";
    msg.textContent =
      "Game: " +
      selectedWordCount +
      " words, " +
      (selectedWordCount + 5) +
      " guesses. (Board coming in Phase 3)";
    board.appendChild(msg);
  }

  function newGame() {
    selectedDifficulty = null;
    selectedWordCount = null;
    selectDifficulty(null);
    selectWordCount(null);
    byId("kwGame").classList.add("kw-hidden");
    byId("kwSetup").classList.remove("kw-hidden");
    updateStartButton();
  }

  function init() {
    loadData();

    all(".kw-difficulty-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectDifficulty(btn.dataset.difficulty);
      });
    });

    all(".kw-word-count-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectWordCount(parseInt(btn.dataset.count, 10));
      });
    });

    const startBtn = byId("kwStartBtn");
    if (startBtn) startBtn.addEventListener("click", startGame);

    const newGameBtn = byId("kwNewGameBtn");
    if (newGameBtn) newGameBtn.addEventListener("click", newGame);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

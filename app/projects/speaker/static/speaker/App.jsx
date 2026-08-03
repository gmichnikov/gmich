import React, { useState, useRef, useEffect } from "react";
import { Settings, X, Volume2, Delete, RotateCcw, Play, MessageSquareText, Star, Keyboard } from "lucide-react";

// ---- Phrase library, grouped by category ----
const PHRASE_GROUPS = [
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

// ---- Flattened list with stable ids, used throughout the app ----
const COMMON_PHRASES = PHRASE_GROUPS.flatMap((group, gi) =>
  group.phrases.map((text, i) => ({ id: `p${gi}-${i}`, text, category: group.category }))
);

// ---- Word-token version of every phrase, used to drive "what usually comes next" predictions ----
const stripPunct = (w) => w.replace(/[?,.!]+$/, "");
const PHRASES = COMMON_PHRASES.map((p) => p.text.split(" ").map(stripPunct));

const DEFAULT_FAVORITE_TEXTS = [
  "Please take me to the bathroom",
  "I am cold",
  "I want coffee",
  "It hurts here",
  "I don't understand",
  "What time is it?",
];
const DEFAULT_FAVORITES = COMMON_PHRASES.filter((p) =>
  DEFAULT_FAVORITE_TEXTS.includes(p.text)
).map((p) => p.id);

// ---- Core vocabulary grid (fixed alphabetical positions — motor memory matters) ----
// 13 words that already matched a phrase, kept as-is: Again, Bathroom, Feel, Go, Help,
// I, It, Need, Please, Thank you, That, Want, You.
// 5 words kept by request even though unused: Yes, No, Done, More, Wait.
// 12 words swapped in to replace the other unused ones — the most common words in the
// phrase list that weren't covered yet: the, to, my, me, is, a, am, cold, don't, too, turn, what.
const CORE_WORDS = [
  "A", "Again", "Am", "Bathroom",
  "Bring", "Cold", "Don't", "Done",
  "Feel", "Give", "Go", "Help",
  "I", "Is", "It", "Me",
  "More", "My", "Need", "No",
  "Please", "Thank you", "That", "The",
  "To", "Too", "Turn", "Wait",
  "Want", "What", "Yes", "You",
].sort((a, b) => a.localeCompare(b));

function buildPredictions(sentence) {
  const lower = sentence.map((w) => w.toLowerCase());
  const counts = new Map();
  for (const phrase of PHRASES) {
    const pLower = phrase.map((w) => w.toLowerCase());
    if (pLower.length <= lower.length) continue;
    let matches = true;
    for (let i = 0; i < lower.length; i++) {
      if (pLower[i] !== lower[i]) { matches = false; break; }
    }
    if (matches) {
      const nextWord = phrase[lower.length];
      counts.set(nextWord, (counts.get(nextWord) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([word]) => word)
    .slice(0, 6);
}

export default function AACCommunicator() {
  const [sentence, setSentence] = useState([]);
  const [volume, setVolume] = useState(0.85);
  const [speakMode, setSpeakMode] = useState("submit"); // "immediate" | "submit"
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [phrasesOpen, setPhrasesOpen] = useState(false);
  const [keyboardOpen, setKeyboardOpen] = useState(false);
  const [letterBuffer, setLetterBuffer] = useState("");
  const [favorites, setFavorites] = useState(DEFAULT_FAVORITES);
  const [favoritesLoaded, setFavoritesLoaded] = useState(false);
  const voicesRef = useRef([]);

  useEffect(() => {
    const loadVoices = () => { voicesRef.current = window.speechSynthesis?.getVoices?.() || []; };
    loadVoices();
    if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = loadVoices;
  }, []);

  // Load saved favorite phrases on first render
  useEffect(() => {
    (async () => {
      try {
        const result = await window.storage.get("favorite-phrase-ids");
        if (result && result.value) {
          setFavorites(JSON.parse(result.value));
        }
      } catch (err) {
        // no saved favorites yet, keep defaults
      } finally {
        setFavoritesLoaded(true);
      }
    })();
  }, []);

  // Persist favorites whenever they change (after initial load)
  useEffect(() => {
    if (!favoritesLoaded) return;
    (async () => {
      try {
        await window.storage.set("favorite-phrase-ids", JSON.stringify(favorites));
      } catch (err) {
        // storage unavailable, favorites just won't persist this session
      }
    })();
  }, [favorites, favoritesLoaded]);

  const speak = (text) => {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.volume = volume;
    utter.rate = 0.95;
    window.speechSynthesis.speak(utter);
  };

  const addWord = (word) => {
    setSentence((prev) => [...prev, word]);
    if (speakMode === "immediate") speak(word);
  };

  const speakSentence = () => {
    if (sentence.length === 0) return;
    speak(sentence.join(" "));
  };

  const usePhrase = (text) => {
    const words = text.split(" ");
    setSentence(words);
    setPhrasesOpen(false);
    if (speakMode === "immediate") speak(text);
  };

  const toggleFavorite = (id) => {
    setFavorites((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const backspace = () => setSentence((prev) => prev.slice(0, -1));
  const clearAll = () => setSentence([]);

  const addLetter = (letter) => setLetterBuffer((prev) => prev + letter);
  const backspaceLetter = () => setLetterBuffer((prev) => prev.slice(0, -1));
  const commitSpelledWord = () => {
    const word = letterBuffer.trim();
    if (word.length > 0) addWord(word);
    setLetterBuffer("");
  };

  const predictions = buildPredictions(sentence);
  const favoritePhrases = COMMON_PHRASES.filter((p) => favorites.includes(p.id));
  const categories = [...new Set(COMMON_PHRASES.map((p) => p.category))];

  return (
    <div className="min-h-screen w-full flex flex-col" style={{ background: "#EEF2F5" }}>
      {/* Top bar: sentence strip + controls */}
      <div className="w-full px-4 pt-4 pb-3" style={{ background: "#FFFFFF", borderBottom: "2px solid #D7DEE3" }}>
        <div className="flex items-start gap-3">
          <div
            className="flex-1 min-h-[64px] rounded-2xl px-4 py-3 flex flex-wrap items-center gap-2"
            style={{ background: "#F5F7F8", border: "2px solid #C7D1D8" }}
            aria-live="polite"
          >
            {sentence.length === 0 ? (
              <span style={{ color: "#8A97A0", fontSize: "20px" }}>Tap words to build a sentence...</span>
            ) : (
              sentence.map((w, i) => (
                <span key={i} style={{ fontSize: "22px", fontWeight: 600, color: "#1F2937" }}>
                  {w}
                </span>
              ))
            )}
          </div>
          <button
            onClick={() => setPhrasesOpen(true)}
            aria-label="Common phrases"
            className="rounded-2xl flex items-center justify-center flex-shrink-0"
            style={{ width: 56, height: 56, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
          >
            <MessageSquareText size={24} color="#3F4A52" />
          </button>
          <button
            onClick={() => setKeyboardOpen(true)}
            aria-label="Spell a word"
            className="rounded-2xl flex items-center justify-center flex-shrink-0"
            style={{ width: 56, height: 56, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
          >
            <Keyboard size={24} color="#3F4A52" />
          </button>
          <button
            onClick={() => setSettingsOpen(true)}
            aria-label="Settings"
            className="rounded-2xl flex items-center justify-center flex-shrink-0"
            style={{ width: 56, height: 56, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
          >
            <Settings size={26} color="#3F4A52" />
          </button>
        </div>

        <div className="flex gap-3 mt-3">
          <button
            onClick={speakSentence}
            disabled={sentence.length === 0}
            className="flex items-center justify-center gap-2 rounded-2xl flex-1"
            style={{
              height: 64,
              background: sentence.length === 0 ? "#F3D9CD" : "#E8734A",
              color: "#FFFFFF",
              fontSize: "22px",
              fontWeight: 700,
              opacity: sentence.length === 0 ? 0.6 : 1,
            }}
          >
            <Play size={26} fill="#FFFFFF" /> Speak
          </button>
          <button
            onClick={backspace}
            aria-label="Delete last word"
            className="flex items-center justify-center rounded-2xl"
            style={{ height: 64, width: 72, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
          >
            <Delete size={26} color="#3F4A52" />
          </button>
          <button
            onClick={clearAll}
            aria-label="Clear sentence"
            className="flex items-center justify-center rounded-2xl"
            style={{ height: 64, width: 72, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
          >
            <RotateCcw size={24} color="#3F4A52" />
          </button>
        </div>
      </div>

      {/* Prediction strip */}
      <div className="w-full px-4 py-2" style={{ minHeight: 64, background: "#FDF6E3", borderBottom: "2px solid #F0E4B8" }}>
        {predictions.length > 0 ? (
          <>
            <div style={{ fontSize: "12px", color: "#8A7433", fontWeight: 600, marginBottom: 4, letterSpacing: "0.03em" }}>
              SUGGESTED NEXT
            </div>
            <div className="flex gap-2 flex-wrap">
              {predictions.map((word) => (
                <button
                  key={word}
                  onClick={() => addWord(word)}
                  className="rounded-full px-4 py-2"
                  style={{ background: "#F5DE9A", color: "#5C4A12", fontSize: "18px", fontWeight: 600, border: "2px solid #E8CB6E" }}
                >
                  {word}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div style={{ fontSize: "14px", color: "#B3A15C", paddingTop: 6 }}>No suggestions yet — start tapping words below</div>
        )}
      </div>

      {/* Favorite phrases quick-access strip */}
      {favoritePhrases.length > 0 && (
        <div className="w-full px-4 py-2" style={{ background: "#E9F3EF", borderBottom: "2px solid #CFE6DC" }}>
          <div style={{ fontSize: "12px", color: "#2F6B52", fontWeight: 600, marginBottom: 4, letterSpacing: "0.03em" }}>
            YOUR PHRASES
          </div>
          <div className="flex gap-2 flex-wrap">
            {favoritePhrases.map((p) => (
              <button
                key={p.id}
                onClick={() => usePhrase(p.text)}
                className="rounded-full px-4 py-2"
                style={{ background: "#FFFFFF", color: "#215A40", fontSize: "17px", fontWeight: 600, border: "2px solid #A9D6C2" }}
              >
                {p.text}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Core vocabulary grid — fixed alphabetical positions */}
      <div className="flex-1 p-4">
        <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
          {CORE_WORDS.map((word) => (
            <button
              key={word}
              onClick={() => addWord(word)}
              className="rounded-2xl flex items-center justify-center text-center px-2"
              style={{
                minHeight: 84,
                background: "#FFFFFF",
                border: "2px solid #C7D1D8",
                fontSize: "20px",
                fontWeight: 600,
                color: "#1F2937",
              }}
            >
              {word}
            </button>
          ))}
        </div>
      </div>

      {/* Spelling keyboard panel */}
      {keyboardOpen && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.4)", zIndex: 50 }}
          onClick={() => setKeyboardOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl p-6 w-full max-w-lg"
            style={{ background: "#FFFFFF", maxHeight: "85vh", overflowY: "auto" }}
          >
            <div className="flex items-center justify-between mb-2">
              <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#1F2937" }}>Spell a word</h2>
              <button onClick={() => setKeyboardOpen(false)} aria-label="Close keyboard">
                <X size={24} color="#3F4A52" />
              </button>
            </div>
            <p style={{ fontSize: "14px", color: "#6B7680", marginBottom: 12 }}>
              Tap letters to spell, then Add word to put it in your sentence.
            </p>

            <div
              className="rounded-2xl px-4 py-3 mb-4 flex items-center"
              style={{ minHeight: 56, background: "#F5F7F8", border: "2px solid #C7D1D8" }}
              aria-live="polite"
            >
              <span style={{ fontSize: "24px", fontWeight: 600, color: letterBuffer ? "#1F2937" : "#8A97A0" }}>
                {letterBuffer || "..."}
              </span>
            </div>

            <div className="grid gap-2 mb-3" style={{ gridTemplateColumns: "repeat(6, 1fr)" }}>
              {"ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("").map((letter) => (
                <button
                  key={letter}
                  onClick={() => addLetter(letter)}
                  className="rounded-xl flex items-center justify-center"
                  style={{
                    minHeight: 52,
                    background: "#FFFFFF",
                    border: "2px solid #C7D1D8",
                    fontSize: "20px",
                    fontWeight: 600,
                    color: "#1F2937",
                  }}
                >
                  {letter}
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => addLetter(" ")}
                className="rounded-xl flex-1 flex items-center justify-center"
                style={{ height: 56, background: "#F5F7F8", border: "2px solid #C7D1D8", fontSize: "16px", fontWeight: 600, color: "#1F2937" }}
              >
                Space
              </button>
              <button
                onClick={backspaceLetter}
                aria-label="Delete last letter"
                className="rounded-xl flex items-center justify-center"
                style={{ height: 56, width: 64, background: "#FFFFFF", border: "2px solid #C7D1D8" }}
              >
                <Delete size={22} color="#3F4A52" />
              </button>
              <button
                onClick={commitSpelledWord}
                disabled={letterBuffer.trim().length === 0}
                className="rounded-xl flex-1 flex items-center justify-center"
                style={{
                  height: 56,
                  background: letterBuffer.trim().length === 0 ? "#F3D9CD" : "#E8734A",
                  color: "#FFFFFF",
                  fontSize: "16px",
                  fontWeight: 700,
                  opacity: letterBuffer.trim().length === 0 ? 0.6 : 1,
                }}
              >
                Add word
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Common phrases panel */}
      {phrasesOpen && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.4)", zIndex: 50 }}
          onClick={() => setPhrasesOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl p-6 w-full max-w-md"
            style={{ background: "#FFFFFF", maxHeight: "80vh", overflowY: "auto" }}
          >
            <div className="flex items-center justify-between mb-2">
              <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#1F2937" }}>Common phrases</h2>
              <button onClick={() => setPhrasesOpen(false)} aria-label="Close phrases">
                <X size={24} color="#3F4A52" />
              </button>
            </div>
            <p style={{ fontSize: "14px", color: "#6B7680", marginBottom: 16 }}>
              Tap a phrase to use it. Tap the star to keep it as a quick-access button on the main screen.
            </p>

            {categories.map((cat) => (
              <div key={cat} className="mb-5">
                <div style={{ fontSize: "13px", fontWeight: 700, color: "#8A97A0", marginBottom: 8, letterSpacing: "0.03em" }}>
                  {cat.toUpperCase()}
                </div>
                <div className="flex flex-col gap-2">
                  {COMMON_PHRASES.filter((p) => p.category === cat).map((p) => {
                    const isFav = favorites.includes(p.id);
                    return (
                      <div
                        key={p.id}
                        className="flex items-center gap-2 rounded-xl"
                        style={{ border: "2px solid #C7D1D8", background: "#F5F7F8" }}
                      >
                        <button
                          onClick={() => usePhrase(p.text)}
                          className="flex-1 text-left px-4 py-3"
                          style={{ fontSize: "17px", fontWeight: 600, color: "#1F2937" }}
                        >
                          {p.text}
                        </button>
                        <button
                          onClick={() => toggleFavorite(p.id)}
                          aria-label={isFav ? "Remove from quick access" : "Add to quick access"}
                          className="flex items-center justify-center flex-shrink-0"
                          style={{ width: 48, height: 48 }}
                        >
                          <Star
                            size={22}
                            color={isFav ? "#E8A23A" : "#B7C0C7"}
                            fill={isFav ? "#E8A23A" : "none"}
                          />
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Settings panel */}
      {settingsOpen && (
        <div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{ background: "rgba(0,0,0,0.4)", zIndex: 50 }}
          onClick={() => setSettingsOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="rounded-2xl p-6 w-full max-w-sm"
            style={{ background: "#FFFFFF" }}
          >
            <div className="flex items-center justify-between mb-5">
              <h2 style={{ fontSize: "20px", fontWeight: 700, color: "#1F2937" }}>Settings</h2>
              <button onClick={() => setSettingsOpen(false)} aria-label="Close settings">
                <X size={24} color="#3F4A52" />
              </button>
            </div>

            <div className="mb-6">
              <div className="flex items-center gap-2 mb-2">
                <Volume2 size={20} color="#3F4A52" />
                <label style={{ fontSize: "16px", fontWeight: 600, color: "#1F2937" }}>Volume</label>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={volume}
                onChange={(e) => setVolume(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            <div>
              <label style={{ fontSize: "16px", fontWeight: 600, color: "#1F2937", display: "block", marginBottom: 8 }}>
                When to speak
              </label>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => setSpeakMode("immediate")}
                  className="rounded-xl px-4 py-3 text-left"
                  style={{
                    background: speakMode === "immediate" ? "#E8734A" : "#F5F7F8",
                    color: speakMode === "immediate" ? "#FFFFFF" : "#1F2937",
                    fontSize: "16px",
                    fontWeight: 600,
                    border: "2px solid " + (speakMode === "immediate" ? "#E8734A" : "#C7D1D8"),
                  }}
                >
                  Speak each word as it's tapped
                </button>
                <button
                  onClick={() => setSpeakMode("submit")}
                  className="rounded-xl px-4 py-3 text-left"
                  style={{
                    background: speakMode === "submit" ? "#E8734A" : "#F5F7F8",
                    color: speakMode === "submit" ? "#FFFFFF" : "#1F2937",
                    fontSize: "16px",
                    fontWeight: 600,
                    border: "2px solid " + (speakMode === "submit" ? "#E8734A" : "#C7D1D8"),
                  }}
                >
                  Build sentence, then speak
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
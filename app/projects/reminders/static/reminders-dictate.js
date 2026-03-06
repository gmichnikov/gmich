(function () {
  const btn = document.getElementById('reminders-mic-btn');
  const input = document.getElementById('title');
  const status = document.getElementById('reminders-mic-status');

  if (!btn || !input) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    btn.disabled = true;
    btn.title = 'Speech recognition is not supported in this browser';
    btn.classList.add('reminders-mic-btn--unsupported');
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  let isRecording = false;
  let savedValue = '';

  function setStatus(msg, hidden) {
    status.textContent = msg;
    status.hidden = !!hidden;
  }

  function startRecording() {
    savedValue = input.value;
    isRecording = true;
    btn.classList.add('reminders-mic-btn--recording');
    btn.title = 'Stop dictation';
    setStatus('Listening…');
    recognition.start();
  }

  function stopRecording() {
    isRecording = false;
    recognition.stop();
    btn.classList.remove('reminders-mic-btn--recording');
    btn.title = 'Dictate title';
    setStatus('', true);
  }

  btn.addEventListener('click', function () {
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  });

  recognition.addEventListener('result', function (e) {
    let interim = '';
    let final = '';

    for (let i = 0; i < e.results.length; i++) {
      const transcript = e.results[i][0].transcript;
      if (e.results[i].isFinal) {
        final += transcript;
      } else {
        interim += transcript;
      }
    }

    input.value = final || interim;
  });

  recognition.addEventListener('error', function (e) {
    let msg = 'Microphone error.';
    if (e.error === 'not-allowed') msg = 'Microphone access denied.';
    else if (e.error === 'no-speech') msg = 'No speech detected.';
    setStatus(msg);
    isRecording = false;
    btn.classList.remove('reminders-mic-btn--recording');
    btn.title = 'Dictate title';
  });

  recognition.addEventListener('end', function () {
    if (isRecording) {
      stopRecording();
    }
  });
})();

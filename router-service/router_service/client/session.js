let ws = null;
let sessionId = null;

function showForm() {
  document.getElementById('form').style.display = 'block';
  document.getElementById('startBtn').disabled = true;
}

function cancelForm() {
  document.getElementById('form').style.display = 'none';
  document.getElementById('startBtn').disabled = false;
}

async function startSession() {
  const projectMap = document.getElementById('projectMap').value.trim();
  const goals = document.getElementById('goals').value.trim();

  setStatus('Connecting…');
  document.getElementById('form').style.display = 'none';

  const resp = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      project_map: projectMap ? [projectMap] : [],
      goals: goals ? [goals] : [],
    }),
  });
  const { session_id } = await resp.json();
  sessionId = session_id;

  ws = new WebSocket(`ws://${location.host}/sessions/${session_id}/audio`);
  ws.binaryType = 'arraybuffer';

  ws.onopen = async () => {
    setStatus('Listening');
    document.getElementById('endBtn').disabled = false;
    await startMic((pcmBuffer) => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send(pcmBuffer);
    });
  };

  ws.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) {
      setStatus('Speaking');
      playPCM(event.data);
    } else {
      const msg = JSON.parse(event.data);
      handleControlFrame(msg);
    }
  };

  ws.onclose = () => {
    stopMic();
    setStatus('Ended');
    document.getElementById('endBtn').disabled = true;
    document.getElementById('startBtn').disabled = false;
  };

  ws.onerror = () => setStatus('Error — check console');
}

async function endSession() {
  if (sessionId) {
    await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  }
  if (ws) ws.close();
  stopMic();
  setStatus('Ended');
  document.getElementById('endBtn').disabled = true;
  document.getElementById('startBtn').disabled = false;
}

function handleControlFrame(msg) {
  switch (msg.type) {
    case 'turn_complete':
      setStatus('Listening');
      break;
    case 'interrupted':
      flushPlayback();
      setStatus('Listening');
      break;
    case 'transcript':
      appendTranscript(msg.role, msg.text);
      break;
    case 'whisper':
      if (document.getElementById('debugToggle').checked) {
        appendWhisper(msg.source, msg.message);
      }
      break;
  }
}

function appendTranscript(role, text) {
  const div = document.getElementById('transcript');
  const line = document.createElement('div');
  line.className = role;
  line.textContent = `${role === 'user' ? 'You' : 'Dev Partner'}: ${text}`;
  div.appendChild(line);
  div.scrollTop = div.scrollHeight;
}

function appendWhisper(source, message) {
  const div = document.getElementById('transcript');
  const line = document.createElement('div');
  line.className = 'whisper';
  line.textContent = `[${source} →] ${message}`;
  div.appendChild(line);
  div.scrollTop = div.scrollHeight;
}

function setStatus(text) {
  document.getElementById('status').textContent = text;
}

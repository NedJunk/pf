let ws = null;
let sessionId = null;

const STATE_LABELS = {
  ready: 'Ready',
  connecting: 'Connecting',
  listening: 'Listening',
  speaking: 'Speaking',
  ended: 'Ended',
  error: 'Error',
};

function setState(state, errorDetail = '') {
  const dot = document.getElementById('dot');
  const label = document.getElementById('status-label');
  const detail = document.getElementById('error-detail');
  const startBtn = document.getElementById('start-btn');
  const endBtn = document.getElementById('end-btn');

  dot.dataset.state = state;
  dot.textContent = state === 'error' ? '⚠' : '⬤';
  label.dataset.state = state;
  label.textContent = STATE_LABELS[state] || state;
  detail.textContent = errorDetail;

  const inCall = state === 'listening' || state === 'speaking';
  startBtn.style.display = inCall ? 'none' : 'block';
  endBtn.style.display = inCall ? 'block' : 'none';
}

async function startSession() {
  setState('connecting');
  try {
    const resp = await fetch('/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_map: [], goals: [] }),
    });
    if (!resp.ok) {
      setState('error', 'Connection error');
      return;
    }
    const { session_id } = await resp.json();
    sessionId = session_id;

    ws = new WebSocket(`ws://${location.host}/sessions/${session_id}/audio`);
    ws.binaryType = 'arraybuffer';

    ws.onopen = async () => {
      setState('listening');
      try {
        await startMic((pcmBuffer) => {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(pcmBuffer);
        });
      } catch (err) {
        setState('error', 'Mic error');
        endSession();
      }
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        setState('speaking');
        playPCM(event.data);
      } else {
        handleControlFrame(JSON.parse(event.data));
      }
    };

    ws.onclose = () => {
      stopMic();
      setState('ended');
    };

    ws.onerror = () => setState('error', 'Connection error');

  } catch (_) {
    setState('error', 'Connection error');
  }
}

async function endSession() {
  try {
    if (sessionId) await fetch(`/sessions/${sessionId}`, { method: 'DELETE' });
  } catch (_) {
    // ignore — proceed with local cleanup regardless
  } finally {
    if (ws) ws.close();
    stopMic();
    setState('ended');
    sessionId = null;
    ws = null;
  }
}

function handleControlFrame(msg) {
  switch (msg.type) {
    case 'turn_complete':
      setState('listening');
      break;
    case 'interrupted':
      flushPlayback();
      setState('listening');
      break;
  }
}

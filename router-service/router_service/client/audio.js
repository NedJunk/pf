const SAMPLE_RATE_IN = 16000;
const SAMPLE_RATE_OUT = 24000;

const WORKLET_CODE = `
class PCMProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    const pcm = new Int16Array(ch.length);
    for (let i = 0; i < ch.length; i++) {
      pcm[i] = Math.max(-32768, Math.min(32767, ch[i] * 32768));
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}
registerProcessor('pcm-processor', PCMProcessor);
`;

let audioCtxIn = null;
let audioCtxOut = null;
let workletNode = null;
let micStream = null;
let onPCMChunk = null;
let playbackTime = 0;

async function startMic(onChunk) {
  onPCMChunk = onChunk;
  const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
  const url = URL.createObjectURL(blob);

  audioCtxIn = new AudioContext({ sampleRate: SAMPLE_RATE_IN });
  await audioCtxIn.audioWorklet.addModule(url);

  micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const source = audioCtxIn.createMediaStreamSource(micStream);
  workletNode = new AudioWorkletNode(audioCtxIn, 'pcm-processor');
  workletNode.port.onmessage = (e) => onPCMChunk && onPCMChunk(e.data);
  source.connect(workletNode);
}

function stopMic() {
  if (workletNode) { workletNode.disconnect(); workletNode = null; }
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null; }
  if (audioCtxIn) { audioCtxIn.close(); audioCtxIn = null; }
}

function playPCM(arrayBuffer) {
  if (!audioCtxOut) audioCtxOut = new AudioContext({ sampleRate: SAMPLE_RATE_OUT });
  const pcm = new Int16Array(arrayBuffer);
  const floats = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) floats[i] = pcm[i] / 32768;
  const buf = audioCtxOut.createBuffer(1, floats.length, SAMPLE_RATE_OUT);
  buf.copyToChannel(floats, 0);
  const src = audioCtxOut.createBufferSource();
  src.buffer = buf;
  src.connect(audioCtxOut.destination);
  const now = audioCtxOut.currentTime;
  if (playbackTime < now) playbackTime = now;
  src.start(playbackTime);
  playbackTime += buf.duration;
}

function flushPlayback() {
  if (audioCtxOut) {
    audioCtxOut.close();
    audioCtxOut = null;
    playbackTime = 0;
  }
}

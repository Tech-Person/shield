// Voice channel audio cues - synthesized with Web Audio API (no external files)
let audioCtx = null;

function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

export function playJoinSound() {
  try {
    const ctx = getAudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(440, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(880, ctx.currentTime + 0.1);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch {}
}

export function playLeaveSound() {
  try {
    const ctx = getAudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.linearRampToValueAtTime(440, ctx.currentTime + 0.15);
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.25);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.25);
  } catch {}
}

// ─── CALL RINGING (looping) ───
let activeRingtone = null;

export function playRingtone() {
  stopRingtone();
  try {
    const ctx = getAudioCtx();
    const gainNode = ctx.createGain();
    gainNode.connect(ctx.destination);
    gainNode.gain.setValueAtTime(0.18, ctx.currentTime);

    let stopped = false;
    const playBurst = (startTime) => {
      if (stopped) return;
      // Two-tone ring: 440Hz then 480Hz, classic phone ring
      for (let i = 0; i < 2; i++) {
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.value = i === 0 ? 440 : 480;
        osc.connect(gainNode);
        osc.start(startTime);
        osc.stop(startTime + 0.8);
      }
    };

    // Ring pattern: 0.8s ring, 1.2s pause, repeat
    const interval = setInterval(() => {
      if (stopped) return;
      playBurst(ctx.currentTime);
    }, 2000);

    playBurst(ctx.currentTime);

    activeRingtone = {
      stop: () => {
        stopped = true;
        clearInterval(interval);
        gainNode.disconnect();
        activeRingtone = null;
      }
    };
  } catch {}
}

export function stopRingtone() {
  if (activeRingtone) {
    activeRingtone.stop();
    activeRingtone = null;
  }
}

let activeDialtone = null;

export function playDialtone() {
  stopDialtone();
  try {
    const ctx = getAudioCtx();
    const gainNode = ctx.createGain();
    gainNode.connect(ctx.destination);
    gainNode.gain.setValueAtTime(0.08, ctx.currentTime);

    let stopped = false;
    const playBeep = (startTime) => {
      if (stopped) return;
      const osc = ctx.createOscillator();
      osc.type = 'sine';
      osc.frequency.value = 425;
      osc.connect(gainNode);
      osc.start(startTime);
      osc.stop(startTime + 0.4);
    };

    const interval = setInterval(() => {
      if (stopped) return;
      playBeep(ctx.currentTime);
    }, 3000);

    playBeep(ctx.currentTime);

    activeDialtone = {
      stop: () => {
        stopped = true;
        clearInterval(interval);
        gainNode.disconnect();
        activeDialtone = null;
      }
    };
  } catch {}
}

export function stopDialtone() {
  if (activeDialtone) {
    activeDialtone.stop();
    activeDialtone = null;
  }
}

// Audio level detection for speaking indicator
export function createAudioLevelDetector(stream, onLevel) {
  try {
    const ctx = getAudioCtx();
    const source = ctx.createMediaStreamSource(stream);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.5;
    source.connect(analyser);
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    let animId = null;

    const check = () => {
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
      const avg = sum / dataArray.length;
      onLevel(avg > 15); // speaking if average above threshold
      animId = requestAnimationFrame(check);
    };
    check();

    return () => {
      if (animId) cancelAnimationFrame(animId);
      source.disconnect();
    };
  } catch {
    return () => {};
  }
}

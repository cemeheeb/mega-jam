// Один проигрыватель на всю Студию. Звук идёт через Web Audio: петля крутится без паузы на стыке,
// поэтому по ней слышно, бесшовный ли звук (у тега <audio> на стыке бывает щель).
import { downloadUrl, fileUrl } from './api.js';

function savedVolume() {
  try {
    const v = Number(localStorage.getItem('studio.volume'));
    return v >= 0 && v <= 1 && localStorage.getItem('studio.volume') !== null ? v : 0.8;
  } catch {
    return 0.8;
  }
}

// track: { key, url, peaks, title, sub, assetId, loop }; queue — список для «предыдущий / следующий»
export const player = $state({ track: null, queue: [], playing: false, loading: false, time: 0, duration: 0, loop: false, volume: savedVolume(), error: '' });

let ctx = null;
let gain = null;
let source = null;
let buffer = null;
let startedAt = 0;
let offset = 0;
let token = 0;
let raf = 0;
const buffers = new Map(); // url -> Promise<AudioBuffer>, несколько последних

function audio() {
  if (!ctx) {
    ctx = new AudioContext();
    gain = ctx.createGain();
    gain.gain.value = player.volume;
    gain.connect(ctx.destination);
  }
  if (ctx.state === 'suspended') ctx.resume();
  return ctx;
}

function decode(url) {
  if (buffers.has(url)) {
    const hit = buffers.get(url);
    buffers.delete(url);
    buffers.set(url, hit);
    return hit;
  }
  const job = fetch(url)
    .then((r) => {
      if (!r.ok) throw new Error(`файл не загрузился (${r.status})`);
      return r.arrayBuffer();
    })
    .then((data) => ctx.decodeAudioData(data))
    .catch((e) => {
      buffers.delete(url);
      throw new Error(e.name === 'EncodingError' ? 'браузер не смог декодировать этот формат' : e.message);
    });
  buffers.set(url, job);
  while (buffers.size > 4) buffers.delete(buffers.keys().next().value);
  return job;
}

function position() {
  if (!player.playing || !buffer) return offset;
  const t = ctx.currentTime - startedAt;
  return player.loop ? t % buffer.duration : Math.min(t, buffer.duration);
}

function stopSource() {
  cancelAnimationFrame(raf);
  if (!source) return;
  source.onended = null;
  try {
    source.stop();
  } catch {
    // ещё не запущен
  }
  source.disconnect();
  source = null;
}

function tick() {
  player.time = position();
  raf = requestAnimationFrame(tick);
}

function startAt(at) {
  stopSource();
  source = ctx.createBufferSource();
  source.buffer = buffer;
  source.loop = player.loop;
  source.connect(gain);
  source.onended = () => {
    source = null;
    cancelAnimationFrame(raf);
    player.playing = false;
    offset = 0;
    player.time = 0;
  };
  offset = at;
  startedAt = ctx.currentTime - at;
  source.start(0, at);
  player.playing = true;
  tick();
}

/** Играть дорожку с начала или с доли at (0…1). queue заменяет список для «предыдущий / следующий». */
export async function play(track, { queue = null, at = 0 } = {}) {
  const my = ++token;
  audio();
  stopSource();
  buffer = null;
  offset = 0;
  if (queue) player.queue = queue;
  Object.assign(player, { track, loop: Boolean(track.loop), playing: false, loading: true, time: 0, duration: 0, error: '' });
  try {
    const b = await decode(track.url);
    if (my !== token) return;
    buffer = b;
    player.loading = false;
    player.duration = b.duration;
    startAt(Math.max(0, Math.min(at, 0.999)) * b.duration);
  } catch (e) {
    if (my !== token) return;
    player.loading = false;
    player.error = e.message;
  }
}

export function pause() {
  if (!player.playing) return;
  offset = position();
  stopSource();
  player.playing = false;
  player.time = offset;
}

export function resume() {
  if (!player.track || player.loading) return;
  if (!buffer) return play(player.track);
  audio();
  startAt(offset >= buffer.duration - 0.005 ? 0 : offset);
}

/** Кнопка ▶ у дорожки: своя играет — пауза, чужая — запустить эту. */
export function toggle(track, opts) {
  if (player.track?.key !== track.key) return play(track, opts);
  if (player.loading) return;
  return player.playing ? pause() : resume();
}

export function seek(frac) {
  if (!buffer) return;
  const at = Math.max(0, Math.min(frac, 0.999)) * buffer.duration;
  if (player.playing) startAt(at);
  else player.time = offset = at;
}

export function setLoop(on) {
  const at = position();
  player.loop = on;
  if (player.playing) startAt(at);
}

export function setVolume(v) {
  player.volume = v;
  if (gain) gain.gain.value = v;
  try {
    localStorage.setItem('studio.volume', String(v));
  } catch {
    // без памяти громкости
  }
}

export function step(d) {
  const q = player.queue;
  if (!q.length) return;
  const i = q.findIndex((t) => t.key === player.track?.key);
  play(q[(i + d + q.length) % q.length]);
}

export function close() {
  token++;
  stopSource();
  buffer = null;
  offset = 0;
  Object.assign(player, { track: null, playing: false, loading: false, time: 0, duration: 0, error: '' });
}

// Волна с сервера: { duration, peaks[] }. Одна загрузка на адрес.
const waves = new Map();
export function loadWave(url) {
  if (!waves.has(url)) {
    const job = fetch(url).then((r) => (r.ok ? r.json() : { duration: 0, peaks: null }));
    job.catch(() => waves.delete(url));
    waves.set(url, job);
  }
  return waves.get(url);
}

const waveUrl = (params) => `/api/peaks?${new URLSearchParams(params)}`;

function assetTrack(asset, rel, f, sub) {
  const url = fileUrl(asset.id, rel, f.mtime);
  return { key: url, url, peaks: waveUrl({ id: asset.id, path: rel, v: String(Math.round(f.mtime)) }), title: asset.title, sub, assetId: asset.id, loop: asset.loop };
}

export const takeTrack = (asset, f) => assetTrack(asset, `takes/${f.name}`, f, `дубль ${f.name}${f.name === asset.take ? ' · в игре' : ''}`);
export const readyTrack = (asset, f) => assetTrack(asset, f.name, f, `для Unreal · ${f.name}`);

export function downloadTrack(f) {
  const url = downloadUrl(f.name, f.mtime);
  return { key: url, url, peaks: waveUrl({ download: f.name, v: String(Math.round(f.mtime)) }), title: f.name, sub: 'из Загрузок', assetId: null, loop: false };
}

/** Что играет карточка звука: готовый S_*.wav, иначе выбранный дубль, иначе самый свежий. */
export function mainTrack(asset) {
  if (asset.kind !== 'sound') return null;
  if (asset.sounds?.length) return readyTrack(asset, asset.sounds[0]);
  const takes = asset.takes ?? [];
  const chosen = takes.find((f) => f.name === asset.take) ?? [...takes].sort((x, y) => y.mtime - x.mtime)[0];
  return chosen ? takeTrack(asset, chosen) : null;
}

/** 1.4 с — для коротких, 2:05 — для длинных. */
export function fmt(sec) {
  if (!sec || !Number.isFinite(sec)) return sec === 0 ? '0.0 с' : '';
  if (sec < 60) return `${sec.toFixed(1)} с`;
  const s = Math.floor(sec % 60);
  return `${Math.floor(sec / 60)}:${String(s).padStart(2, '0')}`;
}

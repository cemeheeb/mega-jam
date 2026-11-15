// Волна звука для проигрывателя Студии: длительность и огибающая громкости.
// Декодирует afconvert (macOS, тот же, что делает S_*.wav): в моно 16 бит 4 кГц — для картинки этого хватает.

import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';

const run = promisify(execFile);
const RATE = 4000;
export const BUCKETS = 160;

/** PCM из WAV: ищет куски fmt и data (afconvert вставляет между ними FLLR). Только целые 16 бит. */
export function parseWav(buf) {
  if (buf.length < 12 || buf.toString('latin1', 0, 4) !== 'RIFF' || buf.toString('latin1', 8, 12) !== 'WAVE') {
    throw new Error('это не WAV');
  }
  let fmt = null;
  for (let at = 12; at + 8 <= buf.length; ) {
    const id = buf.toString('latin1', at, at + 4);
    const size = buf.readUInt32LE(at + 4);
    const body = at + 8;
    if (id === 'fmt ') {
      fmt = { format: buf.readUInt16LE(body), channels: buf.readUInt16LE(body + 2), rate: buf.readUInt32LE(body + 4), bits: buf.readUInt16LE(body + 14) };
    } else if (id === 'data') {
      if (!fmt || fmt.format !== 1 || fmt.bits !== 16) throw new Error('ожидался PCM 16 бит');
      return { ...fmt, data: buf.subarray(body, Math.min(buf.length, body + size)) };
    }
    at = body + size + (size % 2);
  }
  throw new Error('в WAV нет звука');
}

/** Пик по модулю в каждом из buckets отрезков, 0…1. Каналы складываются в один. */
export function envelope({ channels, rate, data }, buckets = BUCKETS) {
  const frames = Math.floor(data.length / (2 * channels));
  const peaks = new Array(buckets).fill(0);
  for (let i = 0; i < frames; i++) {
    const b = Math.min(buckets - 1, Math.floor((i * buckets) / frames));
    for (let c = 0; c < channels; c++) {
      const v = Math.abs(data.readInt16LE((i * channels + c) * 2)) / 32768;
      if (v > peaks[b]) peaks[b] = v;
    }
  }
  return { duration: frames / rate, peaks: peaks.map((p) => Math.round(p * 1000) / 1000) };
}

// Не больше трёх afconvert разом: при первом открытии волну просят все карточки звуков сразу.
let active = 0;
const waiting = [];
async function limited(fn) {
  if (active >= 3) await new Promise((r) => waiting.push(r));
  active++;
  try {
    return await fn();
  } finally {
    active--;
    waiting.shift()?.();
  }
}

const cache = new Map(); // «путь|mtime» -> Promise<{ duration, peaks }>
let serial = 0;

export function peaks(file, mtime) {
  const key = `${file}|${mtime}`;
  if (cache.has(key)) return cache.get(key);
  const job = limited(async () => {
    const tmp = path.join(os.tmpdir(), `studio-wave-${process.pid}-${++serial}.wav`);
    try {
      await run('/usr/bin/afconvert', ['-f', 'WAVE', '-d', `LEI16@${RATE}`, '-c', '1', file, tmp]);
      return envelope(parseWav(await fs.readFile(tmp)));
    } finally {
      await fs.unlink(tmp).catch(() => {});
    }
  });
  job.catch(() => cache.delete(key));
  cache.set(key, job);
  if (cache.size > 600) cache.delete(cache.keys().next().value);
  return job;
}

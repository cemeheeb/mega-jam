// HTTP-интерфейс Студии. Работает только с папкой ассетов и с Загрузками.

import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { promisify } from 'node:util';
import YAML from 'yaml';
import { peaks } from './audio.js';
import { AUDIO_EXT, FIELDS, IMAGE_EXT, KINDS, MODEL_EXT, expandHome, loadAsset, loadConfig, pascal, scan } from './scan.js';

const run = promisify(execFile);
const MAX_UPLOAD = 300 * 1024 * 1024;

const MIME = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.ogg': 'audio/ogg',
  '.flac': 'audio/flac',
  '.m4a': 'audio/mp4',
};

class HttpError extends Error {
  constructor(status, message, extra = {}) {
    super(message);
    this.status = status;
    this.extra = extra;
  }
}

function send(res, status, body) {
  res.statusCode = status;
  res.setHeader('content-type', 'application/json; charset=utf-8');
  res.end(JSON.stringify(body));
}

async function readBody(req, limit = MAX_UPLOAD) {
  const chunks = [];
  let size = 0;
  for await (const c of req) {
    size += c.length;
    if (size > limit) throw new HttpError(413, 'файл слишком большой');
    chunks.push(c);
  }
  return Buffer.concat(chunks);
}

/** Путь внутри base. Всё, что выходит наружу, отклоняется. */
function inside(base, rel) {
  const full = path.resolve(base, rel);
  if (full !== base && !full.startsWith(base + path.sep)) throw new HttpError(400, 'путь вне папки');
  return full;
}

function baseName(name) {
  const b = path.basename(String(name ?? ''));
  if (!b || b.startsWith('.')) throw new HttpError(400, 'плохое имя файла');
  return b;
}

export function slug(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Настоящий формат картинки по первым байтам: генераторы отдают WebP с расширением .png. */
export function imageExt(buf) {
  if (buf.length >= 12 && buf.toString('latin1', 0, 4) === 'RIFF' && buf.toString('latin1', 8, 12) === 'WEBP') return '.webp';
  if (buf.length >= 8 && buf.readUInt32BE(0) === 0x89504e47) return '.png';
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8) return '.jpg';
  return null;
}

async function exists(p) {
  try {
    await fs.access(p);
    return true;
  } catch {
    return false;
  }
}

async function move(src, dest) {
  try {
    await fs.rename(src, dest);
  } catch (e) {
    if (e.code !== 'EXDEV') throw e;
    await fs.copyFile(src, dest);
    await fs.unlink(src);
  }
}

async function freeName(dir, name) {
  const ext = path.extname(name);
  const stem = name.slice(0, name.length - ext.length);
  let candidate = name;
  for (let n = 2; await exists(path.join(dir, candidate)); n++) candidate = `${stem}-${n}${ext}`;
  return candidate;
}

async function toTrash(file) {
  const trash = process.env.STUDIO_TRASH || path.join(os.homedir(), '.Trash'); // своя Корзина — для тестов
  await move(file, path.join(trash, await freeName(trash, path.basename(file))));
}

async function writeYaml(file, mutate) {
  let doc;
  try {
    doc = YAML.parseDocument(await fs.readFile(file, 'utf8'));
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
    doc = new YAML.Document({});
  }
  if (doc.errors.length) throw new HttpError(409, `asset.yml не читается: ${doc.errors[0].message}`);
  if (!YAML.isMap(doc.contents)) doc.contents = doc.createNode({});
  mutate(doc);
  const tmp = `${file}.tmp`;
  await fs.writeFile(tmp, doc.toString({ lineWidth: 0 }), 'utf8');
  await fs.rename(tmp, file);
}

export function createApi({ root }) {
  root = path.resolve(root);

  async function assetDir(id) {
    if (typeof id !== 'string' || !id || id.split('/').some((p) => !p || p.startsWith('.'))) {
      throw new HttpError(400, 'плохой ID ассета');
    }
    const dir = inside(root, id);
    if (!(await exists(path.join(dir, 'asset.yml')))) throw new HttpError(404, `ассет ${id} не найден`);
    return dir;
  }

  async function nextImageName(dir, id, ext) {
    const name = id.split('/').at(-1);
    const images = path.join(dir, 'images');
    await fs.mkdir(images, { recursive: true });
    const used = (await fs.readdir(images))
      .map((f) => new RegExp(`^${name}-(\\d+)\\.`).exec(f))
      .filter(Boolean)
      .map((m) => Number(m[1]));
    return path.join(images, `${name}-${Math.max(0, ...used) + 1}${ext}`);
  }

  /** Имя следующего дубля звука: takes/<имя ассета>-N.<расширение>. */
  async function nextTakeName(dir, id, ext) {
    const name = id.split('/').at(-1);
    const takes = path.join(dir, 'takes');
    await fs.mkdir(takes, { recursive: true });
    const used = (await fs.readdir(takes))
      .map((f) => new RegExp(`^${name}-(\\d+)\\.`).exec(f))
      .filter(Boolean)
      .map((m) => Number(m[1]));
    return path.join(takes, `${name}-${Math.max(0, ...used) + 1}${ext}`);
  }

  async function storeModel(dir, name, place) {
    const tripo = path.join(dir, 'source', 'tripo');
    await fs.mkdir(tripo, { recursive: true });
    const dest = path.join(tripo, await freeName(tripo, name));
    await place(dest);
    if (dest.toLowerCase().endsWith('.zip')) {
      await run('/usr/bin/unzip', ['-o', '-q', dest, '-d', tripo]);
      await toTrash(dest);
    }
  }

  const routes = {
    'GET /state': async () => scan(root),

    'GET /file': async (req, res, q) => {
      const dir = await assetDir(q.get('id'));
      const file = inside(dir, q.get('path') ?? '');
      const type = MIME[path.extname(file).toLowerCase()];
      if (!type) throw new HttpError(400, 'отдаются только картинки и звук');
      const data = await fs.readFile(file).catch(() => {
        throw new HttpError(404, 'файл не найден');
      });
      res.statusCode = 200;
      res.setHeader('content-type', type);
      res.setHeader('cache-control', 'private, max-age=31536000, immutable');
      res.end(data);
      return null;
    },

    'GET /download': async (req, res, q) => {
      const config = await loadConfig(root);
      const file = path.join(expandHome(config.downloads), baseName(q.get('name')));
      const type = MIME[path.extname(file).toLowerCase()];
      if (!type) throw new HttpError(400, 'отдаются только картинки');
      const data = await fs.readFile(file).catch(() => {
        throw new HttpError(404, 'файл не найден');
      });
      res.statusCode = 200;
      res.setHeader('content-type', imageExt(data) === '.webp' ? 'image/webp' : type);
      res.end(data);
      return null;
    },

    // Волна для проигрывателя: файл ассета (id + path) или звук из Загрузок (download).
    'GET /peaks': async (req, res, q) => {
      let file;
      if (q.get('download')) {
        const config = await loadConfig(root);
        file = path.join(expandHome(config.downloads), baseName(q.get('download')));
      } else {
        file = inside(await assetDir(q.get('id')), q.get('path') ?? '');
      }
      if (!AUDIO_EXT.includes(path.extname(file).toLowerCase())) throw new HttpError(400, 'волна строится только для звука');
      const st = await fs.stat(file).catch(() => {
        throw new HttpError(404, 'файл не найден');
      });
      const wave = await peaks(file, st.mtimeMs).catch((e) => {
        throw new HttpError(415, `звук не читается: ${String(e.stderr || e.message).trim().slice(0, 200)}`);
      });
      res.setHeader('cache-control', 'private, max-age=31536000, immutable');
      return wave;
    },

    'POST /assets': async (req, res, q, body) => {
      const title = String(body.title ?? '').trim();
      if (!title) throw new HttpError(400, 'нужно название');
      const kind = KINDS.includes(body.kind) ? body.kind : 'model';
      const name = slug(body.name || title);
      if (!name) throw new HttpError(400, 'ID — латиница и цифры: напишите название по-английски или задайте ID');
      const group = String(body.group ?? '')
        .split('/')
        .map(slug)
        .filter(Boolean)
        .join('/');
      const id = group ? `${group}/${name}` : name;
      const dir = inside(root, id);
      if (await exists(path.join(dir, 'asset.yml'))) throw new HttpError(409, `ассет ${id} уже есть`);
      await fs.mkdir(dir, { recursive: true });
      const fields = { title, kind };
      if (body.idea) fields.idea = String(body.idea);
      if (body.prompt) fields.prompt = String(body.prompt);
      await fs.writeFile(path.join(dir, 'asset.yml'), YAML.stringify(fields, { lineWidth: 0 }), 'utf8');
      return { id };
    },

    'POST /asset/update': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const fields = body.fields ?? {};
      for (const k of Object.keys(fields)) {
        if (!FIELDS.includes(k)) throw new HttpError(400, `поле ${k} не редактируется`);
      }
      if ('kind' in fields && !KINDS.includes(fields.kind)) throw new HttpError(400, 'вид — model, texture или sound');
      if (fields.style && !(await loadConfig(root)).styles[fields.style]) throw new HttpError(400, `стиля ${fields.style} нет в studio.yml`);
      if (fields.image) {
        const img = inside(path.join(dir, 'images'), baseName(fields.image));
        if (!(await exists(img))) throw new HttpError(404, 'такой картинки нет');
      }
      await writeYaml(path.join(dir, 'asset.yml'), (doc) => {
        for (const [k, v] of Object.entries(fields)) {
          const empty = v === null || v === false || (typeof v === 'string' && !v.trim());
          if (empty && k !== 'title') doc.delete(k);
          else doc.set(k, typeof v === 'string' ? v.replace(/\r\n/g, '\n').trimEnd() : v);
        }
      });
      return { ok: true };
    },

    // Забрать файл из Загрузок: картинку в images/, меш в source/tripo/.
    'POST /asset/take': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const config = await loadConfig(root);
      const name = baseName(body.name);
      const src = path.join(expandHome(config.downloads), name);
      if (!(await exists(src))) throw new HttpError(404, 'файла уже нет в Загрузках');
      if (body.as === 'image') {
        const head = Buffer.alloc(16);
        const fh = await fs.open(src);
        await fh.read(head, 0, 16, 0);
        await fh.close();
        const ext = imageExt(head);
        if (!ext) throw new HttpError(400, 'это не PNG, JPEG или WebP');
        await move(src, await nextImageName(dir, body.id, ext));
      } else if (body.as === 'tripo') {
        if (!MODEL_EXT.includes(path.extname(name).toLowerCase())) throw new HttpError(400, 'это не файл модели');
        await storeModel(dir, name, (dest) => move(src, dest));
      } else if (body.as === 'take') {
        const ext = path.extname(name).toLowerCase();
        if (!AUDIO_EXT.includes(ext)) throw new HttpError(400, 'это не звуковой файл');
        await move(src, await nextTakeName(dir, body.id, ext));
      } else {
        throw new HttpError(400, 'as: image, tripo или take');
      }
      return { ok: true };
    },

    // Вставка из буфера и перетаскивание: тело запроса — сам файл.
    'POST /asset/upload': async (req, res, q) => {
      const id = q.get('id');
      const dir = await assetDir(id);
      const data = await readBody(req);
      if (!data.length) throw new HttpError(400, 'пустой файл');
      const ext = imageExt(data);
      if (ext) {
        await fs.writeFile(await nextImageName(dir, id, ext), data);
        return { ok: true, as: 'image' };
      }
      const name = baseName(q.get('name'));
      const audio = path.extname(name).toLowerCase();
      if (AUDIO_EXT.includes(audio)) {
        await fs.writeFile(await nextTakeName(dir, id, audio), data);
        return { ok: true, as: 'take' };
      }
      if (!MODEL_EXT.includes(path.extname(name).toLowerCase())) {
        throw new HttpError(400, 'принимаются картинки (PNG, JPEG, WebP), модели (FBX, GLB, OBJ, ZIP) и звук (MP3, WAV, OGG)');
      }
      await storeModel(dir, name, (dest) => fs.writeFile(dest, data));
      return { ok: true, as: 'tripo' };
    },

    // В Корзину macOS, не удаление: оттуда можно вернуть.
    'POST /asset/trash': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const rel = String(body.path ?? '');
      if (!/^(images|takes|source\/tripo)\/[^/]+$/.test(rel)) throw new HttpError(400, 'в Корзину идут только картинки, дубли звука и меши Tripo');
      const file = inside(dir, rel);
      if (!(await exists(file))) throw new HttpError(404, 'файл не найден');
      await toTrash(file);
      if (rel.startsWith('images/')) {
        const a = await loadAsset(root, body.id);
        if (a.image === path.basename(rel)) await writeYaml(path.join(dir, 'asset.yml'), (doc) => doc.delete('image'));
      }
      return { ok: true };
    },

    // Утверждённая картинка становится текстурой T_<Имя>_BaseColor.png.
    'POST /asset/texture': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const a = await loadAsset(root, body.id);
      if (!a.image) throw new HttpError(400, 'сначала утвердите картинку');
      const src = inside(path.join(dir, 'images'), a.image);
      const destName = `T_${pascal(a.name)}_BaseColor.png`;
      const dest = path.join(dir, destName);
      if ((await exists(dest)) && !body.force) {
        throw new HttpError(409, `${destName} уже есть`, { needsForce: true });
      }
      if (path.extname(src).toLowerCase() === '.png') await fs.copyFile(src, dest);
      else await run('/usr/bin/sips', ['-s', 'format', 'png', src, '--out', dest]);
      return { ok: true, name: destName };
    },

    // Выбранный дубль становится S_<Имя>.wav: 48 кГц, 16 бит — так его берёт Unreal (MP3 он не импортирует).
    'POST /asset/sound': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const a = await loadAsset(root, body.id);
      const name = baseName(body.name);
      const src = inside(path.join(dir, 'takes'), name);
      if (!(await exists(src))) throw new HttpError(404, 'дубль не найден');
      const destName = `S_${pascal(a.name)}.wav`;
      const dest = path.join(dir, destName);
      if ((await exists(dest)) && !body.force) {
        throw new HttpError(409, `${destName} уже есть`, { needsForce: true });
      }
      await run('/usr/bin/afconvert', ['-f', 'WAVE', '-d', 'LEI16@48000', src, dest]);
      await writeYaml(path.join(dir, 'asset.yml'), (doc) => doc.set('take', name));
      return { ok: true, name: destName };
    },

    'POST /open': async (req, res, q, body) => {
      const dir = await assetDir(body.id);
      const config = await loadConfig(root);
      if (body.target === 'folder') {
        await run('/usr/bin/open', [dir]);
      } else if (body.target === 'reveal') {
        const file = inside(dir, String(body.path ?? ''));
        if (!(await exists(file))) throw new HttpError(404, 'файл не найден');
        await run('/usr/bin/open', ['-R', file]);
      } else if (body.target === 'blender') {
        const file = inside(dir, String(body.path ?? ''));
        if (!file.toLowerCase().endsWith('.blend') || !(await exists(file))) throw new HttpError(404, 'blend не найден');
        await run('/usr/bin/open', ['-a', expandHome(config.blender), file]);
      } else {
        throw new HttpError(400, 'target: folder, reveal или blender');
      }
      return { ok: true };
    },
  };

  return async function handle(req, res, next) {
    const url = new URL(req.url, 'http://studio');
    const route = routes[`${req.method} ${url.pathname}`];
    if (!route) return next ? next() : send(res, 404, { error: 'нет такого адреса' });
    try {
      let body = {};
      if (req.method === 'POST') {
        // Свой заголовок не даёт чужой странице в браузере дёргать Студию.
        if (req.headers['x-studio'] !== '1') throw new HttpError(403, 'запрос не от Студии');
        if (url.pathname !== '/asset/upload') {
          const raw = await readBody(req, 1024 * 1024);
          body = raw.length ? JSON.parse(raw.toString('utf8')) : {};
        }
      }
      const result = await route(req, res, url.searchParams, body);
      if (result !== null) send(res, 200, result);
    } catch (e) {
      send(res, e.status ?? 500, { error: e.message, ...(e.extra ?? {}) });
    }
  };
}

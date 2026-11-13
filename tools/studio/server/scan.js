// Сканирование папок ассетов и вычисление этапа по файлам.
// Папка с asset.yml — это ассет. Этап никто не ставит руками: он следует из того, какие файлы лежат.

import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import YAML from 'yaml';

export const IMAGE_EXT = ['.png', '.jpg', '.jpeg', '.webp'];
export const MODEL_EXT = ['.fbx', '.glb', '.gltf', '.obj', '.zip', '.usdz', '.stl'];
export const KINDS = ['model', 'texture'];
export const FIELDS = ['title', 'kind', 'style', 'idea', 'prompt', 'avoid', 'image', 'notes', 'later'];

const STEPS = {
  model: ['idea', 'prompt', 'image', 'tripo', 'blend', 'ready'],
  texture: ['idea', 'prompt', 'image', 'ready'],
};

const DEFAULT_CONFIG = {
  downloads: '~/Downloads',
  blender: '/Applications/Blender.app',
  // Стили промта: имя -> { title, model, texture }. В шаблоне {prompt} — описание из asset.yml.
  styles: {},
  // Стиль по папке: 'environment' -> 'interior'. Побеждает самая длинная подходящая папка.
  folders: {},
  default_style: '',
};

/** Стиль ассета: свой из asset.yml, иначе по папке, иначе стиль по умолчанию. */
export function resolveStyle(config, id, own) {
  const styles = config?.styles ?? {};
  if (own && styles[own]) return own;
  let best = '';
  for (const folder of Object.keys(config?.folders ?? {})) {
    const hit = id === folder || id.startsWith(folder + '/');
    if (hit && folder.length > best.length && styles[config.folders[folder]]) best = folder;
  }
  if (best) return config.folders[best];
  if (styles[config?.default_style]) return config.default_style;
  return Object.keys(styles)[0] ?? '';
}

/** Этап, шаги и следующий ход. Чистая функция: на вход то, что нашлось в папке. */
export function derive(a) {
  const kind = a.kind === 'texture' ? 'texture' : 'model';
  const has = {
    idea: true,
    prompt: Boolean(a.prompt && String(a.prompt).trim()),
    image: Boolean(a.image) && a.images.some((i) => i.name === a.image),
    tripo: a.tripo.length > 0,
    blend: a.blends.length > 0,
    ready: kind === 'model' ? a.meshes.length > 0 : a.textures.length > 0,
  };
  const keys = STEPS[kind];
  let last = 0;
  keys.forEach((k, i) => {
    if (has[k]) last = i;
  });
  const steps = keys.map((key, i) => ({
    key,
    state: has[key] ? 'done' : i < last ? 'skipped' : i === last + 1 ? 'next' : 'todo',
  }));
  const nextKey = keys[last + 1];
  let next = null;
  if (nextKey === 'prompt') next = { step: nextKey, who: 'claude', label: 'нужен промт' };
  if (nextKey === 'image') {
    next = a.images.length
      ? { step: nextKey, who: 'author', label: 'утвердить картинку' }
      : { step: nextKey, who: 'author', label: 'нужна картинка' };
  }
  if (nextKey === 'tripo') next = { step: nextKey, who: 'author', label: 'нужен меш Tripo' };
  if (nextKey === 'blend') next = { step: nextKey, who: 'claude', label: 'собрать в Blender' };
  if (nextKey === 'ready') {
    next =
      kind === 'model'
        ? { step: nextKey, who: 'claude', label: 'выгрузить FBX' }
        : { step: nextKey, who: 'author', label: 'сделать текстурой' };
  }

  const warnings = [];
  if (a.kind && !KINDS.includes(a.kind)) warnings.push(`неизвестный вид «${a.kind}», считаю моделью`);
  if (a.image && !has.image) warnings.push(`утверждённая картинка ${a.image} не найдена в images/`);
  if (kind === 'model' && a.blends.length && a.meshes.length) {
    const blend = Math.max(...a.blends.map((f) => f.mtime));
    const mesh = Math.min(...a.meshes.map((f) => f.mtime));
    if (blend > mesh + 1000) warnings.push('blend новее FBX: выгрузка устарела');
  }
  return { kind, steps, stage: keys[last], next, warnings };
}

export function expandHome(p) {
  return p.startsWith('~') ? path.join(os.homedir(), p.slice(1)) : p;
}

export async function loadConfig(root) {
  let user = {};
  try {
    user = YAML.parse(await fs.readFile(path.join(root, 'studio.yml'), 'utf8')) ?? {};
  } catch (e) {
    if (e.code !== 'ENOENT') user = { error: `studio.yml: ${e.message}` };
  }
  const config = { ...DEFAULT_CONFIG, ...user };
  for (const k of ['styles', 'folders']) {
    if (!config[k] || typeof config[k] !== 'object' || Array.isArray(config[k])) config[k] = {};
  }
  return config;
}

async function listFiles(dir, test) {
  let names;
  try {
    names = await fs.readdir(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const out = [];
  for (const d of names) {
    if (!d.isFile() || d.name.startsWith('.') || !test(d.name)) continue;
    const st = await fs.stat(path.join(dir, d.name));
    out.push({ name: d.name, mtime: st.mtimeMs, size: st.size });
  }
  return out.sort((x, y) => x.name.localeCompare(y.name, 'en', { numeric: true }));
}

const hasExt = (list) => (name) => list.includes(path.extname(name).toLowerCase());

/** Все папки с asset.yml под корнем. Внутрь ассета не заходим. */
export async function findAssetIds(root) {
  const ids = [];
  async function walk(rel) {
    let entries;
    try {
      entries = await fs.readdir(path.join(root, rel), { withFileTypes: true });
    } catch {
      return;
    }
    if (rel && entries.some((e) => e.isFile() && e.name === 'asset.yml')) {
      ids.push(rel.split(path.sep).join('/'));
      return;
    }
    for (const e of entries) {
      if (e.isDirectory() && !e.name.startsWith('.') && e.name !== 'node_modules') {
        await walk(path.join(rel, e.name));
      }
    }
  }
  await walk('');
  return ids.sort((x, y) => x.localeCompare(y, 'en', { numeric: true }));
}

export function pascal(name) {
  return name
    .split(/[^A-Za-z0-9]+/)
    .filter(Boolean)
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join('');
}

export async function loadAsset(root, id, config = null) {
  const dir = path.join(root, id);
  const parts = id.split('/');
  const name = parts.at(-1);
  let data = {};
  let parseError = null;
  try {
    data = YAML.parse(await fs.readFile(path.join(dir, 'asset.yml'), 'utf8')) ?? {};
    if (typeof data !== 'object' || Array.isArray(data)) throw new Error('ожидался словарь полей');
  } catch (e) {
    parseError = `asset.yml не читается: ${e.message}`;
    data = {};
  }
  const a = {
    id,
    name,
    group: parts.length > 1 ? parts.slice(0, -1).join('/') : '',
    title: data.title ? String(data.title) : name,
    kind: data.kind ?? 'model',
    style: data.style ? String(data.style) : '',
    idea: data.idea ? String(data.idea) : '',
    prompt: data.prompt ? String(data.prompt) : '',
    // свои запреты ассета: строка через запятую или список
    avoid: Array.isArray(data.avoid) ? data.avoid.join(', ') : data.avoid ? String(data.avoid) : '',
    image: data.image ? String(data.image) : '',
    notes: data.notes ? String(data.notes) : '',
    later: Boolean(data.later),
    images: await listFiles(path.join(dir, 'images'), hasExt(IMAGE_EXT)),
    tripo: await listFiles(path.join(dir, 'source', 'tripo'), (n) => !n.endsWith('.zip')),
    blends: await listFiles(path.join(dir, 'source'), (n) => n.toLowerCase().endsWith('.blend')),
    meshes: await listFiles(dir, (n) => /^SM_.+\.fbx$/i.test(n)),
    textures: await listFiles(dir, (n) => /^T_.+\.(png|tga|exr|jpg)$/i.test(n)),
    preview: (await listFiles(dir, (n) => n === 'preview.png'))[0] ?? null,
  };
  const d = derive(a);
  if (parseError) d.warnings.unshift(parseError);
  if (config && a.style && !config.styles[a.style]) {
    d.warnings.push(`стиля «${a.style}» нет в studio.yml, взят стиль по папке`);
  }
  const thumb = a.preview
    ? { path: 'preview.png', v: a.preview.mtime }
    : a.image && a.images.find((i) => i.name === a.image)
      ? { path: `images/${a.image}`, v: a.images.find((i) => i.name === a.image).mtime }
      : a.images.length
        ? { path: `images/${a.images.at(-1).name}`, v: a.images.at(-1).mtime }
        : a.textures.length
          ? { path: a.textures[0].name, v: a.textures[0].mtime }
          : null;
  return {
    ...a,
    ...d,
    thumb,
    styleResolved: config ? resolveStyle(config, id, a.style) : '',
    unreal: '/Game/' + parts.map(pascal).join('/'),
  };
}

/** Свежие картинки и модели в Загрузках: за последние трое суток, новые первыми. */
export async function listDownloads(config) {
  const dir = expandHome(config.downloads);
  const since = Date.now() - 72 * 3600 * 1000;
  try {
    const all = await listFiles(dir, hasExt([...IMAGE_EXT, ...MODEL_EXT]));
    const fresh = all.filter((f) => f.mtime >= since).sort((x, y) => y.mtime - x.mtime);
    return {
      images: fresh.filter((f) => hasExt(IMAGE_EXT)(f.name)).slice(0, 12),
      models: fresh.filter((f) => hasExt(MODEL_EXT)(f.name)).slice(0, 8),
    };
  } catch (e) {
    return { images: [], models: [], error: `Загрузки недоступны: ${e.message}` };
  }
}

export async function scan(root) {
  const config = await loadConfig(root);
  const ids = await findAssetIds(root);
  const assets = await Promise.all(ids.map((id) => loadAsset(root, id, config)));
  return { root, config, assets, downloads: await listDownloads(config) };
}

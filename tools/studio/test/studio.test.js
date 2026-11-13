import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';
import { createApi, imageExt, slug } from '../server/api.js';
import { derive, pascal, resolveStyle } from '../server/scan.js';
import { fullPrompt } from '../src/lib/prompt.js';

const base = { kind: 'model', prompt: '', image: '', images: [], tripo: [], blends: [], meshes: [], textures: [] };
const f = (name, mtime = 1000) => ({ name, mtime, size: 1 });

test('этап модели следует из файлов', () => {
  assert.equal(derive(base).stage, 'idea');
  assert.equal(derive(base).next.label, 'нужен промт');
  const p = { ...base, prompt: 'A fuse' };
  assert.equal(derive(p).stage, 'prompt');
  assert.deepEqual(derive(p).next, { step: 'image', who: 'author', label: 'нужна картинка' });
  const i = { ...p, images: [f('fuse-1.webp')] };
  assert.equal(derive(i).stage, 'prompt');
  assert.equal(derive(i).next.label, 'утвердить картинку');
  const ok = { ...i, image: 'fuse-1.webp' };
  assert.equal(derive(ok).stage, 'image');
  assert.equal(derive(ok).next.who, 'author');
  const t = { ...ok, tripo: [f('fuse.glb')] };
  assert.equal(derive(t).next.label, 'собрать в Blender');
  const b = { ...t, blends: [f('fuse.blend')] };
  assert.equal(derive(b).next.label, 'выгрузить FBX');
  const r = { ...b, meshes: [f('SM_Fuse.fbx', 2000)] };
  assert.equal(derive(r).stage, 'ready');
  assert.equal(derive(r).next, null);
  assert.deepEqual(derive(r).warnings, []);
});

test('пропущенный шаг не мешает, устаревшая выгрузка видна', () => {
  const d = derive({ ...base, blends: [f('x.blend', 5000)], meshes: [f('SM_X.fbx', 2000)] });
  assert.equal(d.stage, 'ready');
  assert.deepEqual(d.steps.map((s) => s.state), ['done', 'skipped', 'skipped', 'skipped', 'done', 'done']);
  assert.deepEqual(d.warnings, ['blend новее FBX: выгрузка устарела']);
});

test('текстура: четыре шага, утверждённая картинка без файла — замечание', () => {
  const d = derive({ ...base, kind: 'texture', prompt: 'x', image: 'gone.png' });
  assert.deepEqual(d.steps.map((s) => s.key), ['idea', 'prompt', 'image', 'ready']);
  assert.equal(d.stage, 'prompt');
  assert.equal(d.warnings.length, 1);
  const r = derive({ ...base, kind: 'texture', textures: [f('T_X_BaseColor.png')] });
  assert.equal(r.stage, 'ready');
});

test('имена', () => {
  assert.equal(slug('Sealant Can'), 'sealant-can');
  assert.equal(slug('  Фонарь  '), '');
  assert.equal(pascal('sealant-can'), 'SealantCan');
  assert.equal(imageExt(Buffer.from('RIFF\0\0\0\0WEBPVP8 ', 'latin1')), '.webp');
  assert.equal(imageExt(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])), '.png');
  assert.equal(imageExt(Buffer.from('hello')), null);
});

test('стиль: свой, по папке, по умолчанию', () => {
  const config = {
    styles: { interior: {}, prop: {} },
    folders: { environment: 'interior', 'environment/props': 'prop', ghost: 'nope' },
    default_style: 'prop',
  };
  assert.equal(resolveStyle(config, 'items/fuse', ''), 'prop');
  assert.equal(resolveStyle(config, 'environment/walls/column', ''), 'interior');
  assert.equal(resolveStyle(config, 'environment/props/crate', ''), 'prop');
  assert.equal(resolveStyle(config, 'items/fuse', 'interior'), 'interior');
  assert.equal(resolveStyle(config, 'environment/walls/column', 'unknown'), 'interior');
  assert.equal(resolveStyle(config, 'ghost/x', ''), 'prop');
  assert.equal(resolveStyle(config, 'environments/x', ''), 'prop');
  assert.equal(resolveStyle({ styles: {} }, 'a/b', ''), '');
});

test('полный промт: описание и свои запреты встают в шаблон стиля', () => {
  const config = { styles: { prop: { model: 'HEAD\n\n{prompt}\n\nAvoid: text, glow{avoid}.\n', texture: '{prompt} TEX' } } };
  const a = { kind: 'model', styleResolved: 'prop', prompt: ' A fuse. ', avoid: '' };
  assert.equal(fullPrompt(config, a), 'HEAD\n\nA fuse.\n\nAvoid: text, glow.');
  assert.equal(fullPrompt(config, { ...a, avoid: 'sparks,  smoke. ' }), 'HEAD\n\nA fuse.\n\nAvoid: text, glow, sparks, smoke.');
  assert.equal(fullPrompt(config, { ...a, kind: 'texture', avoid: 'seams' }), 'A fuse. TEX\n\nAvoid: seams.');
  assert.equal(fullPrompt({}, a), 'A fuse.');
});

// --- HTTP на временной папке ---

let tmp, root, downloads, server, url;
const WEBP = Buffer.from('RIFF\x10\0\0\0WEBPVP8 \0\0\0\0', 'latin1');

async function post(p, body, raw) {
  const r = await fetch(url + p, {
    method: 'POST',
    headers: { 'x-studio': '1', ...(raw ? {} : { 'content-type': 'application/json' }) },
    body: raw ?? JSON.stringify(body),
  });
  return { status: r.status, body: await r.json() };
}
const state = async () => (await fetch(url + '/state')).json();

before(async () => {
  tmp = await fs.mkdtemp(path.join(os.tmpdir(), 'studio-test-'));
  root = path.join(tmp, 'SourceArt');
  downloads = path.join(tmp, 'Downloads');
  await fs.mkdir(root);
  await fs.mkdir(downloads);
  await fs.writeFile(path.join(root, 'studio.yml'), `downloads: ${downloads}\nstyles:\n  prop:\n    model: "{prompt} STYLE"\n  interior:\n    model: "{prompt} PALETTE"\nfolders:\n  environment: interior\ndefault_style: prop\n`);
  server = http.createServer(createApi({ root }));
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  url = `http://127.0.0.1:${server.address().port}`;
});

after(async () => {
  server.close();
  await fs.rm(tmp, { recursive: true, force: true });
});

test('путь ассета от создания до утверждённой картинки', async () => {
  let r = await post('/assets', { title: 'Sealant Can', kind: 'model', group: 'Items', idea: 'Dented can' });
  assert.deepEqual(r.body, { id: 'items/sealant-can' });
  assert.equal((await post('/assets', { title: 'Sealant Can', group: 'items' })).status, 409);

  r = await post('/asset/update', { id: 'items/sealant-can', fields: { prompt: 'A dented can\nwith stripes' } });
  assert.equal(r.status, 200);
  let s = await state();
  assert.equal(s.assets.length, 1);
  assert.equal(s.assets[0].prompt, 'A dented can\nwith stripes');
  assert.equal(s.assets[0].stage, 'prompt');
  assert.equal(s.assets[0].unreal, '/Game/Items/SealantCan');
  assert.equal(s.config.styles.prop.model, '{prompt} STYLE');
  assert.equal(s.assets[0].styleResolved, 'prop');
  assert.equal((await post('/asset/update', { id: 'items/sealant-can', fields: { style: 'nope' } })).status, 400);
  await post('/asset/update', { id: 'items/sealant-can', fields: { style: 'interior' } });
  assert.equal((await state()).assets[0].styleResolved, 'interior');
  await post('/asset/update', { id: 'items/sealant-can', fields: { style: '' } });
  assert.equal((await state()).assets[0].style, '');

  // картинка из Загрузок: WebP с расширением .png получает настоящее расширение
  await fs.writeFile(path.join(downloads, 'image_1-1.png'), WEBP);
  s = await state();
  assert.deepEqual(s.downloads.images.map((i) => i.name), ['image_1-1.png']);
  r = await post('/asset/take', { id: 'items/sealant-can', name: 'image_1-1.png', as: 'image' });
  assert.equal(r.status, 200);
  await assert.rejects(fs.access(path.join(downloads, 'image_1-1.png')));

  // вставка из буфера
  r = await post('/asset/upload?id=items/sealant-can&name=paste.png', null, WEBP);
  assert.deepEqual(r.body, { ok: true, as: 'image' });
  s = await state();
  assert.deepEqual(s.assets[0].images.map((i) => i.name), ['sealant-can-1.webp', 'sealant-can-2.webp']);
  assert.equal(s.assets[0].next.label, 'утвердить картинку');

  r = await post('/asset/update', { id: 'items/sealant-can', fields: { image: 'sealant-can-2.webp' } });
  assert.equal(r.status, 200);
  s = await state();
  assert.equal(s.assets[0].stage, 'image');
  assert.equal(s.assets[0].thumb.path, 'images/sealant-can-2.webp');
  assert.equal((await post('/asset/update', { id: 'items/sealant-can', fields: { image: 'nope.webp' } })).status, 404);

  // меш Tripo из Загрузок
  await fs.writeFile(path.join(downloads, 'can.glb'), 'glTF');
  r = await post('/asset/take', { id: 'items/sealant-can', name: 'can.glb', as: 'tripo' });
  assert.equal(r.status, 200);
  s = await state();
  assert.equal(s.assets[0].stage, 'tripo');
  assert.equal(s.assets[0].next.label, 'собрать в Blender');

  // комментарии и порядок полей в asset.yml переживают правку
  const yml = path.join(root, 'items/sealant-can/asset.yml');
  await fs.writeFile(yml, '# мой комментарий\n' + (await fs.readFile(yml, 'utf8')));
  await fs.appendFile(yml, 'avoid: [sparks, smoke]\n');
  assert.equal((await state()).assets[0].avoid, 'sparks, smoke');
  await post('/asset/update', { id: 'items/sealant-can', fields: { notes: 'note', idea: '', avoid: 'sparks' } });
  assert.equal((await state()).assets[0].avoid, 'sparks');
  const text = await fs.readFile(yml, 'utf8');
  assert.match(text, /^# мой комментарий\ntitle: Sealant Can\nkind: model\n/);
  assert.doesNotMatch(text, /idea:/);
  assert.match(text, /notes: note/);
});

test('защита: чужие запросы и пути наружу отклоняются', async () => {
  const r = await fetch(url + '/assets', { method: 'POST', body: '{}' });
  assert.equal(r.status, 403);
  assert.equal((await post('/asset/update', { id: '../Downloads', fields: {} })).status, 400);
  assert.equal((await post('/asset/update', { id: 'items/sealant-can', fields: { evil: 1 } })).status, 400);
  assert.equal((await post('/asset/trash', { id: 'items/sealant-can', path: 'asset.yml' })).status, 400);
  assert.equal((await fetch(url + '/file?id=items/sealant-can&path=../../studio.yml')).status, 400);
  assert.equal((await fetch(url + '/file?id=items/sealant-can&path=asset.yml')).status, 400);
  assert.equal((await post('/asset/take', { id: 'items/sealant-can', name: '../../etc/passwd', as: 'tripo' })).status, 404);
});

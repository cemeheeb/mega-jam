async function parse(r) {
  const body = await r.json().catch(() => ({ error: `ошибка ${r.status}` }));
  if (!r.ok) throw Object.assign(new Error(body.error ?? `ошибка ${r.status}`), { status: r.status, body });
  return body;
}

export async function getState() {
  return parse(await fetch('/api/state'));
}

export async function post(path, body) {
  return parse(
    await fetch('/api' + path, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-studio': '1' },
      body: JSON.stringify(body),
    }),
  );
}

export async function upload(id, file) {
  const q = new URLSearchParams({ id, name: file.name || 'paste.png' });
  return parse(await fetch(`/api/asset/upload?${q}`, { method: 'POST', headers: { 'x-studio': '1' }, body: file }));
}

export const fileUrl = (id, path, v = 0) =>
  `/api/file?${new URLSearchParams({ id, path, v: String(Math.round(v)) })}`;

export const downloadUrl = (name, v = 0) =>
  `/api/download?${new URLSearchParams({ name, v: String(Math.round(v)) })}`;

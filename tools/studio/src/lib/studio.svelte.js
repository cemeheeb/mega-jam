import { getState } from './api.js';

export const STAGES = [
  { key: 'idea', label: 'Идея' },
  { key: 'prompt', label: 'Промт' },
  { key: 'image', label: 'Картинка' },
  { key: 'tripo', label: 'Tripo' },
  { key: 'blend', label: 'Blender' },
  { key: 'ready', label: 'Готово' },
];
export const STAGE_LABEL = Object.fromEntries(STAGES.map((s) => [s.key, s.label]));

export const studio = $state({ data: null, error: '', toast: null });

let toastTimer;
export function toast(text, bad = false) {
  studio.toast = { text, bad };
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (studio.toast = null), bad ? 6000 : 2200);
}

export async function refresh() {
  try {
    studio.data = await getState();
    studio.error = '';
  } catch (e) {
    studio.error = `Сервер Студии не отвечает: ${e.message}`;
  }
}

/** Выполнить действие, показать ошибку, обновить данные. */
export async function act(fn, done) {
  try {
    const r = await fn();
    if (done) toast(done);
    return r;
  } catch (e) {
    toast(e.message, true);
    return null;
  } finally {
    await refresh();
  }
}

export function age(ms) {
  const m = Math.round((Date.now() - ms) / 60000);
  if (m < 1) return 'только что';
  if (m < 60) return `${m} мин назад`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h} ч назад`;
  return `${Math.round(h / 24)} дн назад`;
}

export function size(bytes) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

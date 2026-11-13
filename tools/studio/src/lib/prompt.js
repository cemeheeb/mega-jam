// Сборка полного промта: шаблон стиля + описание и свои запреты ассета.
// В шаблоне {prompt} — описание, {avoid} — свои запреты ассета в конце строки Avoid.

export function fullPrompt(config, asset) {
  const tpl = String(config?.styles?.[asset.styleResolved]?.[asset.kind] ?? '{prompt}');
  const own = (asset.avoid ?? '')
    .split(',')
    .map((s) => s.trim().replace(/\.$/, ''))
    .filter(Boolean)
    .join(', ');
  let text = tpl.replace('{prompt}', asset.prompt.trim());
  if (text.includes('{avoid}')) text = text.replace('{avoid}', own ? `, ${own}` : '');
  else if (own) text = `${text.trim()}\n\nAvoid: ${own}.`;
  return text.trim();
}

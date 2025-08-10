export function makeSku(prefix: string | null | undefined, parts: string[]) {
  const p = (prefix ?? '').trim().toUpperCase();
  const middle = parts.map(s => s.replace(/[^A-Za-z0-9]+/g, '').toUpperCase()).filter(Boolean).join('-');
  return [p || 'SKU', middle].filter(Boolean).join('-');
}

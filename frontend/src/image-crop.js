// Show a documented region of the untouched archive image; keep its original URL.
export function imageCrop(src) {
  if (typeof src !== 'string') return null;
  const at = src.indexOf('#hhe-crop=');
  if (at < 0) return null;
  const original = src.slice(0, at);
  if (!/^https?:\/\//i.test(original) && !original.startsWith('/media/')) return null;
  const tokens = src.slice(at + '#hhe-crop='.length).split(',');
  if (tokens.length !== 6 || tokens.some(t => !/^\d+(?:\.\d+)?$/.test(t))) return null;
  const [width, height, x, y, cropWidth, cropHeight] = tokens.map(Number);
  if (![width, height, x, y, cropWidth, cropHeight].every(Number.isFinite)
      || width <= 0 || height <= 0 || width > 100000 || height > 100000
      || cropWidth <= 0 || cropHeight <= 0 || x + cropWidth > width || y + cropHeight > height) return null;
  return { original, width, height, viewBox: `${x} ${y} ${cropWidth} ${cropHeight}` };
}

import React, { useEffect, useId, useRef, useState } from 'react';
import { imageCrop } from './image-crop.js';

export default function ArchiveImage({ src, alt, onError, loading, ...props }) {
  const crop = imageCrop(src);
  const host = useRef(null);
  const clipId = 'archive-crop-' + useId().replace(/:/g, '');
  const [visible, setVisible] = useState(loading !== 'lazy');
  useEffect(() => {
    if (!crop || loading !== 'lazy') return;
    if (typeof IntersectionObserver === 'undefined') { setVisible(true); return; }
    setVisible(false);
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, { rootMargin: '250px' });
    if (host.current) observer.observe(host.current);
    return () => observer.disconnect();
  }, [src, loading, Boolean(crop)]);
  if (!crop) return <img src={src} alt={alt} onError={onError} loading={loading} {...props} />;
  const [x, y, width, height] = crop.viewBox.split(' ');
  return <svg ref={host} className="archive-image-crop" viewBox={crop.viewBox}
    preserveAspectRatio="xMidYMid meet" role="img" aria-label={alt}>
    <title>{alt}</title>
    <defs><clipPath id={clipId} clipPathUnits="userSpaceOnUse">
      <rect x={x} y={y} width={width} height={height} />
    </clipPath></defs>
    {(loading !== 'lazy' || visible) && <image href={crop.original} width={crop.width} height={crop.height} clipPath={`url(#${clipId})`} onError={onError} />}
  </svg>;
}

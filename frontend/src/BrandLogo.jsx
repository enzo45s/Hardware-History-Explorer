import React, { useState, useSyncExternalStore } from 'react';
import { Monitor } from 'lucide-react';

function ThemeLogo({ resolved }) {
  const [unavailable, setUnavailable] = useState(false);
  if (unavailable) return <div className="brand">
    <div className="brand-icon"><Monitor size={22} aria-hidden="true" /></div>
    <div><b>HARDWARE</b><span>HISTORY EXPLORER</span></div>
  </div>;

  return <div className="brand brand-with-logo"><div className="brand-logo-panel">
    <img className="brand-logo" src={`${import.meta.env.BASE_URL}branding/logo-${resolved}.png`}
      alt="Hardware History Explorer" width="2048" height="1230"
      onError={() => setUnavailable(true)} />
  </div></div>;
}

export default function BrandLogo() {
  const theme = window.HardwareHistoryTheme;
  const { resolved } = useSyncExternalStore(theme.subscribe, theme.getSnapshot);
  // Reset image loading/error state when switching to the other theme's asset.
  return <ThemeLogo key={resolved} resolved={resolved} />;
}

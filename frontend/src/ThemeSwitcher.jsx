import React, { useSyncExternalStore } from 'react';
import { Laptop, Sun, Moon } from 'lucide-react';
import './theme.css';

const choices = [
  { value: 'system', label: 'Sistema', Icon: Laptop, title: 'Segui il tema del sistema operativo' },
  { value: 'light', label: 'Chiaro', Icon: Sun, title: 'Usa sempre il tema chiaro' },
  { value: 'dark', label: 'Fosfori verdi', Icon: Moon, title: 'Usa sempre il tema scuro a fosfori verdi' }
];

export default function ThemeSwitcher() {
  const theme = window.HardwareHistoryTheme;
  const { preference } = useSyncExternalStore(theme.subscribe, theme.getSnapshot);
  return <div className="theme-switcher" role="group" aria-label="Tema dell’app">
    {choices.map(({ value, label, Icon, title }) => <button key={value} type="button" aria-label={'Tema: ' + label}
      aria-pressed={preference === value} title={title} onClick={() => theme.setPreference(value)}>
      <Icon size={15} aria-hidden="true" /><span className="theme-button-label">{label}</span>
    </button>)}
  </div>;
}

import React from 'react';
import { ChevronRight } from 'lucide-react';
import { displayDescription } from './catalog-display.js';
import './computer-card.css';

export default function ComputerCard({ computer, Cover, onOpen, onOpenManufacturer, onCompare, selected = false }) {
  const description = displayDescription(computer)?.trim() || 'Descrizione non ancora disponibile.';
  return <article className="catalog-card">
    <Cover src={computer.image_url} name={computer.model_name} year={computer.year} className="catalog-photo" />
    <span className="tag" title={computer.categories?.join(' · ')}>{computer.categories?.[0] || 'Categoria non documentata'}</span>
    <h3 className="catalog-card-title" title={computer.model_name}>{computer.model_name}</h3>
    <div className="catalog-card-meta">
      {onOpenManufacturer
        ? <button className="manufacturer-link" onClick={() => onOpenManufacturer(computer.manufacturer_id)}>{computer.manufacturer}</button>
        : <span>{computer.manufacturer}</span>}
      <span className="catalog-card-date">{computer.first_release || computer.year || 'Data non disponibile'}</span>
    </div>
    <p className="catalog-card-description">{description}</p>
    <div className="card-foot">
      <button onClick={() => onOpen(computer.id)}>Dettagli <ChevronRight size={15} /></button>
      {onCompare && <button onClick={() => onCompare(computer)} className={selected ? 'added' : ''} aria-pressed={selected}>{selected ? '✓' : '+ Confronta'}</button>}
    </div>
  </article>;
}

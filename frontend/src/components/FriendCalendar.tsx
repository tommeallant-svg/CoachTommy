'use client';

import { useState } from 'react';
import { addMonths, addWeeks, eachDayOfInterval, endOfMonth, endOfWeek, format, isSameDay, isSameMonth, parseISO, startOfMonth, startOfWeek, subMonths, subWeeks } from 'date-fns';
import { fr } from 'date-fns/locale';

export type SharedWorkout = { name: string | null; date: string; sport: string | null; duration_minutes: number | null; distance_km: number | null; description: string | null; scheme: unknown[] | null };

export default function FriendCalendar({ workouts }: { workouts: SharedWorkout[] }) {
  const [date, setDate] = useState(new Date());
  const [view, setView] = useState<'week' | 'month'>('week');
  const [selected, setSelected] = useState<SharedWorkout | null>(null);
  const start = startOfWeek(view === 'month' ? startOfMonth(date) : date, { weekStartsOn: 1 });
  const end = endOfWeek(view === 'month' ? endOfMonth(date) : date, { weekStartsOn: 1 });
  const days = eachDayOfInterval({ start, end });
  const button = 'rounded-xl border border-brand-light px-3 py-2 font-bold text-brand-dark hover:bg-brand-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary';

  return <div className="mt-5 space-y-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h3 className="text-lg font-black capitalize text-brand-dark" aria-live="polite">{view === 'month' ? format(date, 'MMMM yyyy', { locale: fr }) : `${format(start, 'd MMM', { locale: fr })} – ${format(end, 'd MMM yyyy', { locale: fr })}`}</h3>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={button} aria-pressed={view === 'week'} onClick={() => setView('week')}>Semaine</button>
        <button type="button" className={button} aria-pressed={view === 'month'} onClick={() => setView('month')}>Mois</button>
        <button type="button" className={button} aria-label="Période précédente" onClick={() => setDate(view === 'week' ? subWeeks(date, 1) : subMonths(date, 1))}>‹</button>
        <button type="button" className={button} onClick={() => setDate(new Date())}>Aujourd’hui</button>
        <button type="button" className={button} aria-label="Période suivante" onClick={() => setDate(view === 'week' ? addWeeks(date, 1) : addMonths(date, 1))}>›</button>
      </div>
    </div>
    <div className="overflow-x-auto rounded-2xl border border-brand-light">
      <div className="min-w-[560px]">
        <div className="grid grid-cols-7 bg-brand-dark text-center text-xs font-black uppercase text-white">{['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'].map(day => <div key={day} className="p-3">{day}</div>)}</div>
        <div className="grid grid-cols-7">
          {days.map(day => <div key={day.toISOString()} className={`min-h-28 border-b border-r border-brand-light p-2 ${view === 'month' && !isSameMonth(day, date) ? 'bg-gray-50' : 'bg-white'}`}>
            <div className={`mb-2 text-sm font-bold ${isSameDay(day, new Date()) ? 'text-brand-primary' : 'text-brand-dark'}`}>{format(day, 'd')}</div>
            <div className="space-y-1">{workouts.filter(workout => isSameDay(parseISO(workout.date), day)).map((workout, index) => <button key={index} type="button" onClick={() => setSelected(workout)} className="w-full rounded-md border-l-[3px] border-brand-primary bg-brand-surface px-2 py-1 text-left text-xs font-bold text-brand-dark hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary"><span className="break-words">{workout.name || 'Séance sans nom'}</span></button>)}</div>
          </div>)}
        </div>
      </div>
    </div>
    {selected && <section className="rounded-xl border border-brand-light p-4" aria-label="Détails de la séance">
      <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="text-lg font-black">{selected.name || 'Séance sans nom'}</h3><button type="button" className={button} onClick={() => setSelected(null)}>Fermer les détails</button></div>
      <dl className="mt-2 space-y-1"><div><dt className="inline font-bold">Date : </dt><dd className="inline">{format(parseISO(selected.date), 'EEEE d MMMM yyyy HH:mm', { locale: fr })}</dd></div><div><dt className="inline font-bold">Sport : </dt><dd className="inline">{selected.sport || 'Non renseigné'}</dd></div><div><dt className="inline font-bold">Durée : </dt><dd className="inline">{selected.duration_minutes != null ? `${selected.duration_minutes} min` : 'Non renseignée'}</dd></div><div><dt className="inline font-bold">Distance : </dt><dd className="inline">{selected.distance_km != null ? `${selected.distance_km} km` : 'Non renseignée'}</dd></div></dl>
      {selected.description && <div className="mt-3"><h4 className="font-bold">Description</h4><p className="whitespace-pre-wrap break-words">{selected.description}</p></div>}
      {selected.scheme && selected.scheme.length > 0 && <div className="mt-3"><h4 className="font-bold">Structure</h4><pre className="overflow-x-auto whitespace-pre-wrap break-words text-sm">{JSON.stringify(selected.scheme, null, 2)}</pre></div>}
    </section>}
  </div>;
}
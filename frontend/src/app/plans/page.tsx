'use client';

import React, { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Archive, ChevronLeft, Plus, Trash2 } from 'lucide-react';
import { fetchWithAuth, getAuthToken } from '@/lib/api';

type Plan = {
  id: number;
  race_name: string;
  race_date: string;
  start_date: string;
  race_distance: number;
  sessions_per_week: number;
  goal_type: string;
  cancellation_comment: string | null;
};

type Week = {
  week_start: string;
  week_end: string;
  workout_count: number;
  validated_count: number;
  duration_minutes: number;
  distance_km: number;
  estimated_load: number;
};

const PAGE_SIZE = 10;
const dateLabel = (date: string) => new Date(`${date.slice(0, 10)}T12:00:00`).toLocaleDateString('fr-FR');

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetchWithAuth(url, options);
  if (!response.ok) {
    let message = `Erreur ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
    } catch { /* La réponse peut ne pas contenir de JSON. */ }
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

function WeeklyStats({ plan }: { plan: Plan }) {
  const [weeks, setWeeks] = useState<Week[] | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setWeeks(null);
    setError('');
    request<Week[]>(`/api/plans/${plan.id}/weekly-stats`)
      .then(data => { if (!cancelled) setWeeks(data); })
      .catch(err => { if (!cancelled) setError(err.message || 'Impossible de charger les statistiques.'); });
    return () => { cancelled = true; };
  }, [plan.id]);

  if (error) return <p role="alert" className="text-red-700">Statistiques : {error}</p>;
  if (!weeks) return <p className="text-brand-secondary">Chargement des statistiques...</p>;
  if (!weeks.length) return <p className="text-brand-secondary">Aucune statistique hebdomadaire disponible.</p>;

  const total = weeks.reduce((sum, week) => sum + week.workout_count, 0);
  const validated = weeks.reduce((sum, week) => sum + week.validated_count, 0);
  const max = Math.max(1, ...weeks.map(week => Math.max(week.workout_count, week.validated_count)));

  return (
    <div className="space-y-5">
      <p className="font-bold text-brand-dark"><span className="text-2xl font-black text-brand-primary">{validated}</span> / {total} séances validées</p>
      <div className="flex flex-wrap gap-4 text-xs font-bold text-brand-secondary">
        <span><span className="inline-block w-3 h-3 rounded-sm bg-brand-light mr-2" />Prévu</span>
        <span><span className="inline-block w-3 h-3 rounded-sm bg-brand-primary mr-2" />Réalisé (validé)</span>
      </div>
      <div className="overflow-x-auto">
        <div className="flex items-end gap-3 min-w-max" aria-label="Séances prévues et réalisées par semaine">
          {weeks.map(week => (
            <div key={week.week_start} className="w-20 text-center text-xs text-brand-secondary">
              <div className="h-36 flex items-end justify-center gap-1 border-b border-brand-light" aria-label={`Semaine du ${dateLabel(week.week_start)} : ${week.workout_count} prévues, ${week.validated_count} réalisées`}>
                <div className="w-6 bg-brand-light rounded-t" style={{ height: `${week.workout_count / max * 100}%` }} title={`${week.workout_count} prévues`} />
                <div className="w-6 bg-brand-primary rounded-t" style={{ height: `${week.validated_count / max * 100}%` }} title={`${week.validated_count} réalisées`} />
              </div>
              <div className="font-bold mt-2">{dateLabel(week.week_start)}</div>
              <div>{week.workout_count} / {week.validated_count}</div>
            </div>
          ))}
        </div>
      </div>
      <p className="text-xs text-brand-secondary">Nombre de séances prévues / validées par semaine.</p>
      <details className="text-sm text-brand-secondary">
        <summary className="cursor-pointer font-bold">Détails hebdomadaires</summary>
        <ul className="mt-3 space-y-2">
          {weeks.map(week => <li key={week.week_start}>Du {dateLabel(week.week_start)} au {dateLabel(week.week_end)} : {week.duration_minutes} min, {week.distance_km.toFixed(1)} km, charge {week.estimated_load.toFixed(1)}</li>)}
        </ul>
      </details>
    </div>
  );
}

function PlansContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const athleteId = searchParams.get('athleteId');
  const athleteQuery = athleteId ? `athlete_id=${encodeURIComponent(athleteId)}` : '';
  const [current, setCurrent] = useState<Plan | null>(null);
  const [history, setHistory] = useState<Plan[]>([]);
  const [page, setPage] = useState(0);
  const [hasNext, setHasNext] = useState(false);
  const [selected, setSelected] = useState<Plan | null>(null);
  const [loadingCurrent, setLoadingCurrent] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [currentError, setCurrentError] = useState('');
  const [historyError, setHistoryError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    if (!getAuthToken()) router.replace('/login');
  }, [router]);

  useEffect(() => {
    setPage(0);
    setSelected(null);
  }, [athleteId]);

  useEffect(() => {
    if (!getAuthToken()) return;
    let cancelled = false;
    setLoadingCurrent(true);
    setCurrentError('');
    setCurrent(null);
    request<Plan | null>(`/api/plans/current${athleteQuery ? `?${athleteQuery}` : ''}`)
      .then(data => { if (!cancelled) setCurrent(data); })
      .catch(err => { if (!cancelled) setCurrentError(err.message || 'Impossible de charger le plan actif.'); })
      .finally(() => { if (!cancelled) setLoadingCurrent(false); });
    return () => { cancelled = true; };
  }, [athleteQuery, refresh]);

  useEffect(() => {
    if (!getAuthToken()) return;
    let cancelled = false;
    setLoadingHistory(true);
    setHistoryError('');
    const params = new URLSearchParams(athleteQuery);
    params.set('skip', String(page * PAGE_SIZE));
    params.set('limit', String(PAGE_SIZE + 1));
    request<Plan[]>(`/api/plans/history?${params}`)
      .then(data => {
        if (!cancelled) {
          setHistory(data.slice(0, PAGE_SIZE));
          setHasNext(data.length > PAGE_SIZE);
        }
      })
      .catch(err => { if (!cancelled) setHistoryError(err.message || 'Impossible de charger les archives.'); })
      .finally(() => { if (!cancelled) setLoadingHistory(false); });
    return () => { cancelled = true; };
  }, [athleteQuery, page, refresh]);

  const changePlan = async (plan: Plan, action: 'archive' | 'delete') => {
    const message = action === 'archive'
      ? `Archiver le plan « ${plan.race_name} » ? Ses séances seront conservées.`
      : `Supprimer définitivement le plan « ${plan.race_name} » et toutes ses séances ? Cette action est irréversible.`;
    if (!window.confirm(message)) return;
    setBusy(true);
    setActionError('');
    try {
      await request(action === 'archive' ? `/api/plans/${plan.id}/archive` : `/api/plans/${plan.id}`, action === 'archive'
        ? { method: 'POST', body: JSON.stringify({ cancellation_comment: null }) }
        : { method: 'DELETE' });
      setSelected(null);
      if (action === 'delete' && history.length === 1 && page > 0 && current?.id !== plan.id) setPage(page - 1);
      setRefresh(value => value + 1);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Action impossible.');
    } finally {
      setBusy(false);
    }
  };

  const creationLink = athleteId ? `/plans/new?athleteId=${encodeURIComponent(athleteId)}` : '/plans/new';
  const dashboardLink = athleteId ? `/?athleteId=${encodeURIComponent(athleteId)}` : '/';
  const card = 'bg-white rounded-[2rem] p-6 md:p-8 shadow-sm border border-brand-light space-y-6';
  const button = 'inline-flex items-center gap-2 px-4 py-3 rounded-xl font-black uppercase text-xs tracking-widest transition-all disabled:opacity-50';

  return (
    <div className="min-h-screen bg-brand-surface pb-20">
      <header className="bg-brand-dark px-6 py-6 shadow-lg">
        <div className="max-w-6xl mx-auto flex flex-wrap items-center justify-between gap-4">
          <Link href={dashboardLink} className="flex items-center gap-2 text-brand-secondary hover:text-white font-black uppercase text-xs tracking-widest"><ChevronLeft className="w-5 h-5" /> Tableau de bord</Link>
          <h1 className="text-2xl font-black text-white uppercase tracking-tighter">Plans</h1>
          <Link href={creationLink} className={`${button} bg-brand-primary text-white hover:bg-brand-secondary`}><Plus className="w-4 h-4" /> Créer un plan</Link>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-6 mt-10 space-y-8">
        {actionError && <p role="alert" className="bg-red-50 text-red-700 rounded-xl p-4">{actionError}</p>}
        <section className={card}>
          <h2 className="text-2xl font-black text-brand-dark uppercase tracking-tight">Plan actif</h2>
          {loadingCurrent ? <p>Chargement du plan...</p> : currentError ? <p role="alert" className="text-red-700">{currentError}</p> : !current ? (
            <p className="text-brand-secondary">Aucun plan actif. <Link href={creationLink} className="text-brand-primary font-bold underline">Créer un plan</Link></p>
          ) : (
            <>
              <PlanSummary plan={current} />
              <WeeklyStats plan={current} />
              <div className="flex flex-wrap gap-3">
                <button disabled={busy} onClick={() => changePlan(current, 'archive')} className={`${button} bg-brand-surface text-brand-dark hover:bg-brand-light`}><Archive className="w-4 h-4" /> Archiver</button>
                <button disabled={busy} onClick={() => changePlan(current, 'delete')} className={`${button} bg-red-50 text-red-700 hover:bg-red-100`}><Trash2 className="w-4 h-4" /> Supprimer</button>
              </div>
            </>
          )}
        </section>
        <section className={card}>
          <h2 className="text-2xl font-black text-brand-dark uppercase tracking-tight">Plans archivés</h2>
          {loadingHistory ? <p>Chargement des archives...</p> : historyError ? <p role="alert" className="text-red-700">{historyError}</p> : history.length === 0 ? <p className="text-brand-secondary">Aucun plan archivé sur cette page.</p> : (
            <div className="space-y-4">
              {history.map(plan => (
                <div key={plan.id} className="bg-brand-surface rounded-2xl p-5 space-y-4">
                  <PlanSummary plan={plan} />
                  {plan.cancellation_comment && <p className="text-sm text-brand-secondary">Commentaire : {plan.cancellation_comment}</p>}
                  <div className="flex flex-wrap gap-3">
                    <button onClick={() => setSelected(selected?.id === plan.id ? null : plan)} className={`${button} bg-white text-brand-primary hover:bg-brand-light`} aria-expanded={selected?.id === plan.id}>{selected?.id === plan.id ? 'Masquer les statistiques' : 'Voir les statistiques'}</button>
                    <button disabled={busy} onClick={() => changePlan(plan, 'delete')} className={`${button} bg-red-50 text-red-700 hover:bg-red-100`}><Trash2 className="w-4 h-4" /> Supprimer</button>
                  </div>
                  {selected?.id === plan.id && <WeeklyStats plan={plan} />}
                </div>
              ))}
            </div>
          )}
          <nav aria-label="Pagination des plans archivés" className="flex items-center gap-4">
            <button disabled={page === 0 || loadingHistory} onClick={() => { setSelected(null); setPage(page - 1); }} className={`${button} bg-brand-surface text-brand-dark`}>Précédent</button>
            <span className="text-sm font-bold text-brand-secondary">Page {page + 1}</span>
            <button disabled={!hasNext || loadingHistory || !!historyError} onClick={() => { setSelected(null); setPage(page + 1); }} className={`${button} bg-brand-surface text-brand-dark`}>Suivant</button>
          </nav>
        </section>
      </main>
    </div>
  );
}

function PlanSummary({ plan }: { plan: Plan }) {
  return <div><h3 className="text-xl font-black text-brand-dark">{plan.race_name}</h3><p className="text-sm font-bold text-brand-secondary mt-2">Du {dateLabel(plan.start_date)} au {dateLabel(plan.race_date)} · {plan.race_distance} km · {plan.sessions_per_week} séances / semaine · {plan.goal_type}</p></div>;
}

export default function PlansPage() {
  return <Suspense fallback={<div className="p-8">Chargement...</div>}><PlansContent /></Suspense>;
}
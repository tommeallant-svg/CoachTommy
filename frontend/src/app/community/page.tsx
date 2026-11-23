'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { fetchWithAuth, getAuthToken } from '@/lib/api';
import FriendCalendar, { SharedWorkout } from '@/components/FriendCalendar';

type Connection = { id: number; person: { id: number; email: string }; direction: 'sent' | 'received' };
type Plan = { workouts: SharedWorkout[] };

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

const button = 'rounded-xl border border-brand-primary px-4 py-2 font-bold text-brand-primary hover:bg-brand-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-primary disabled:opacity-50';

export default function CommunityPage() {
  const router = useRouter();
  const [invitations, setInvitations] = useState<Connection[]>([]);
  const [friends, setFriends] = useState<Connection[]>([]);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [selected, setSelected] = useState<Connection | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');

  async function loadConnections() {
    setLoading(true);
    setError('');
    try {
      const [invitationData, friendData] = await Promise.all([
        request<Connection[]>('/api/community/invitations'),
        request<Connection[]>('/api/community/friends'),
      ]);
      setInvitations(invitationData);
      setFriends(friendData);
      setLoaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Impossible de charger la communauté.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!getAuthToken()) { router.replace('/login'); return; }
    loadConnections();
  }, [router]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setPlan(null);
    setPlanError('');
    setPlanLoading(true);
    request<Plan | null>(`/api/community/friends/${selected.person.id}/plan`)
      .then(data => { if (!cancelled) setPlan(data); })
      .catch(err => { if (!cancelled) setPlanError(err instanceof Error ? err.message : 'Impossible de charger le plan.'); })
      .finally(() => { if (!cancelled) setPlanLoading(false); });
    return () => { cancelled = true; };
  }, [selected]);

  async function mutate(url: string, options: RequestInit, success: string, afterSuccess?: () => void) {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await request(url, options);
      afterSuccess?.();
      setMessage(success);
      await loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action impossible.');
    } finally {
      setBusy(false);
    }
  }

  function invite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void mutate('/api/community/invitations', { method: 'POST', body: JSON.stringify({ email: email.trim() }) }, 'Invitation envoyée.', () => setEmail(''));
  }

  function remove(connection: Connection, success: string) {
    void mutate(`/api/community/connections/${connection.id}`, { method: 'DELETE' }, success, () => {
      if (selected?.id === connection.id) setSelected(null);
    });
  }

  const received = invitations.filter(item => item.direction === 'received');
  const sent = invitations.filter(item => item.direction === 'sent');

  return (
    <main className="min-h-screen bg-brand-surface pb-20">
      <header className="bg-brand-dark px-5 py-8 text-white"><div className="mx-auto max-w-5xl">
        <h1 className="text-3xl font-black">Communauté</h1>
        <p className="mt-3 max-w-3xl">L’acceptation d’une invitation partage réciproquement votre plan actif et celui de votre ami, en lecture seule, y compris les descriptions et structures de séances saisies librement.</p>
      </div></header>
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6">
        <section className="rounded-2xl bg-white p-5 shadow-sm" aria-labelledby="invite-heading">
          <h2 id="invite-heading" className="text-xl font-black text-brand-dark">Inviter une personne</h2>
          <form onSubmit={invite} className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-0 flex-1 basis-64"><label htmlFor="community-email" className="mb-2 block font-bold">Adresse e-mail</label><input id="community-email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} className="w-full rounded-xl border p-3" /></div>
            <button type="submit" disabled={busy} className={button}>Envoyer l’invitation</button>
          </form>
        </section>
        {error && <div role="alert" className="rounded-xl bg-red-50 p-4 text-red-700">{error} <button type="button" className="underline" onClick={loadConnections} disabled={loading || busy}>Réessayer le chargement</button></div>}
        {message && <p role="status">{message}</p>}
        {loading ? <p role="status">Chargement de la communauté...</p> : loaded && <>
          <div className="grid gap-6 md:grid-cols-2">
            <section className="rounded-2xl bg-white p-5 shadow-sm" aria-labelledby="received-heading">
              <h2 id="received-heading" className="text-xl font-black text-brand-dark">Invitations reçues</h2>
              {received.length === 0 ? <p className="mt-4">Aucune invitation reçue.</p> : <ul className="mt-4 space-y-4">{received.map(item => <li key={item.id} className="space-y-2 border-b pb-4 last:border-0"><p className="break-all font-bold">{item.person.email}</p><div className="flex flex-wrap gap-2"><button type="button" className={button} disabled={busy} onClick={() => mutate(`/api/community/invitations/${item.id}/accept`, { method: 'POST' }, 'Invitation acceptée.')}>Accepter <span className="sr-only">l’invitation de {item.person.email}</span></button><button type="button" className={button} disabled={busy} onClick={() => remove(item, 'Invitation refusée.')}>Refuser <span className="sr-only">l’invitation de {item.person.email}</span></button></div></li>)}</ul>}
            </section>
            <section className="rounded-2xl bg-white p-5 shadow-sm" aria-labelledby="sent-heading">
              <h2 id="sent-heading" className="text-xl font-black text-brand-dark">Invitations envoyées</h2>
              {sent.length === 0 ? <p className="mt-4">Aucune invitation envoyée.</p> : <ul className="mt-4 space-y-4">{sent.map(item => <li key={item.id} className="space-y-2 border-b pb-4 last:border-0"><p className="break-all font-bold">{item.person.email}</p><button type="button" className={button} disabled={busy} onClick={() => remove(item, 'Invitation annulée.')}>Annuler <span className="sr-only">l’invitation pour {item.person.email}</span></button></li>)}</ul>}
            </section>
          </div>
          <section className="rounded-2xl bg-white p-5 shadow-sm" aria-labelledby="friends-heading">
            <h2 id="friends-heading" className="text-xl font-black text-brand-dark">Mes amis</h2>
            {friends.length === 0 ? <p className="mt-4">Vous n’avez pas encore d’amis.</p> : <ul className="mt-4 space-y-4">{friends.map(friend => <li key={friend.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-4 last:border-0"><span className="break-all font-bold">{friend.person.email}</span><div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={() => setSelected(friend)}>Voir le plan <span className="sr-only">de {friend.person.email}</span></button><button type="button" className={button} disabled={busy} onClick={() => remove(friend, 'Ami supprimé.')}>Supprimer <span className="sr-only">{friend.person.email}</span></button></div></li>)}</ul>}
          </section>
        </>}
        {selected && <section className="rounded-2xl bg-white p-5 shadow-sm" aria-labelledby="plan-heading">
          <div className="flex flex-wrap items-center justify-between gap-3"><h2 id="plan-heading" className="break-all text-xl font-black text-brand-dark">Plan actif de {selected.person.email}</h2><button type="button" className={button} onClick={() => setSelected(null)}>Fermer le plan</button></div>
          <p className="mt-2 text-sm">Consultation en lecture seule.</p>
          {planLoading ? <p role="status" className="mt-4">Chargement du plan...</p> : planError ? <p role="alert" className="mt-4 text-red-700">{planError} <button type="button" className="underline" onClick={() => setSelected({ ...selected })}>Réessayer</button></p> : !plan ? <p className="mt-4">Aucun plan actif.</p> : <>{plan.workouts.length === 0 && <p className="mt-4">Ce plan ne contient aucune séance.</p>}<FriendCalendar key={selected.person.id} workouts={plan.workouts} /></>}
        </section>}
      </div>
    </main>
  );
}
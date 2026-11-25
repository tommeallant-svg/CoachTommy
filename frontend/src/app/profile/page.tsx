'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Activity, ArrowLeft, LogOut, Watch } from 'lucide-react';
import AthleteStatsModal from '@/components/AthleteStatsModal';
import GarminAuthModal from '@/components/GarminAuthModal';
import { clearAuthToken, fetchWithAuth, getAuthToken } from '@/lib/api';
import { User } from '@/types/user';

async function readResponse(response: Response, fallback: string) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof data.detail === 'string' ? data.detail : fallback);
  }
  return data;
}

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [userError, setUserError] = useState('');
  const [garmin, setGarmin] = useState<{ is_connected: boolean; garmin_email?: string } | null>(null);
  const [garminError, setGarminError] = useState('');
  const [strava, setStrava] = useState<{ connected: boolean; scope?: string | null } | null>(null);
  const [stravaError, setStravaError] = useState('');
  const [stravaBusy, setStravaBusy] = useState(false);
  const [showGarmin, setShowGarmin] = useState(false);
  const [showStats, setShowStats] = useState(false);
  const [aiActive, setAiActive] = useState<boolean | null>(null);
  const [aiError, setAiError] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [aiKey, setAiKey] = useState('');
  const [aiCopied, setAiCopied] = useState(false);

  const loadUser = async () => {
    try {
      const data = await readResponse(await fetchWithAuth('/api/auth/me'), 'Impossible de charger le profil.');
      setUser(data);
      localStorage.setItem('user', JSON.stringify(data));
      setUserError('');
    } catch (error) {
      setUserError(error instanceof Error ? error.message : 'Impossible de charger le profil.');
    }
  };

  const loadGarmin = async () => {
    try {
      const data = await readResponse(await fetchWithAuth('/api/auth/garmin/status'), 'Impossible de charger l’état Garmin.');
      setGarmin(data);
      setGarminError('');
    } catch (error) {
      setGarmin(null);
      setGarminError(error instanceof Error ? error.message : 'Impossible de charger l’état Garmin.');
    }
  };

  const loadStrava = async () => {
    try {
      const data = await readResponse(await fetchWithAuth('/api/auth/strava/status'), 'Impossible de charger l’état Strava.');
      setStrava(data);
      setStravaError('');
    } catch (error) {
      setStrava(null);
      setStravaError(error instanceof Error ? error.message : 'Impossible de charger l’état Strava.');
    }
  };

  useEffect(() => {
    if (!getAuthToken()) {
      router.push('/login');
      return;
    }
    void loadUser();
    void loadGarmin();
    void loadStrava();
  }, [router]);

  const loadAiAccess = async () => {
    setAiError('');
    try {
      const data = await readResponse(await fetchWithAuth('/api/ai-access', { cache: 'no-store' }), 'Impossible de charger l’état de l’accès IA.');
      if (typeof data.active !== 'boolean') throw new Error('Réponse invalide pour l’accès IA.');
      setAiActive(data.active);
    } catch (error) {
      setAiActive(null);
      setAiError(error instanceof Error ? error.message : 'Impossible de charger l’état de l’accès IA.');
    }
  };

  useEffect(() => {
    if (user?.role === 'athlete') void loadAiAccess();
  }, [user?.id, user?.role]);

  const changeAiAccess = async (revoke: boolean) => {
    if (revoke && !window.confirm('Révoquer la clé IA ? Les applications qui l’utilisent perdront immédiatement leur accès.')) return;
    if (!revoke && aiActive && !window.confirm('Renouveler la clé IA ? L’ancienne clé cessera immédiatement de fonctionner.')) return;
    setAiBusy(true);
    setAiError('');
    setAiKey('');
    setAiCopied(false);
    try {
      const response = await fetchWithAuth('/api/ai-access', { method: revoke ? 'DELETE' : 'POST', cache: 'no-store' });
      const data = await readResponse(response, revoke ? 'Impossible de révoquer la clé IA.' : 'Impossible de générer la clé IA.');
      if (!revoke && (typeof data.key !== 'string' || !data.key)) throw new Error('La clé IA n’a pas été reçue. Vérifiez son état et générez-en une nouvelle si nécessaire.');
      setAiActive(!revoke);
      if (!revoke) setAiKey(data.key);
    } catch (error) {
      setAiActive(null);
      setAiError(error instanceof Error ? error.message : 'Une erreur est survenue pour l’accès IA.');
    } finally {
      setAiBusy(false);
    }
  };

  const copyAiKey = async () => {
    try {
      await navigator.clipboard.writeText(aiKey);
      setAiCopied(true);
      setAiError('');
    } catch {
      setAiError('Copie impossible. Sélectionnez et copiez la clé manuellement.');
    }
  };

  const changeStrava = async () => {
    setStravaBusy(true);
    setStravaError('');
    try {
      if (strava?.connected) {
        const data = await readResponse(await fetchWithAuth('/api/auth/strava/disconnect', { method: 'POST' }), 'Impossible de déconnecter Strava.');
        setStrava(data);
      } else {
        const data = await readResponse(await fetchWithAuth('/api/auth/strava/authorize', { method: 'POST' }), 'Impossible de connecter Strava.');
        const url = new URL(data.authorization_url);
        if (url.protocol !== 'https:' || url.hostname !== 'www.strava.com') throw new Error('URL d’autorisation Strava invalide.');
        window.location.assign(url.toString());
      }
    } catch (error) {
      setStravaError(error instanceof Error ? error.message : 'Une erreur Strava est survenue.');
    } finally {
      setStravaBusy(false);
    }
  };

  const buttonClass = 'w-full sm:w-auto rounded-2xl bg-brand-dark px-5 py-3 font-bold text-white hover:bg-brand-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:opacity-50';

  return (
    <main className="min-h-screen bg-brand-surface px-4 py-8 text-brand-dark sm:px-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <Link href="/" className="inline-flex items-center gap-2 font-bold hover:underline"><ArrowLeft className="h-4 w-4" /> Retour au calendrier</Link>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl">Mon profil</h1>

        <section className="space-y-4 rounded-3xl bg-white p-6 shadow-sm" aria-labelledby="stats-title">
          <h2 id="stats-title" className="flex items-center gap-2 text-xl font-black"><Activity className="h-5 w-5" /> Statistiques athlète</h2>
          {userError && <p role="alert" className="text-red-700">{userError} <button className="underline" onClick={loadUser}>Réessayer</button></p>}
          {user ? <>
            <p className="break-all">{user.email}</p>
            <p>VMA : <strong>{user.vma != null ? `${user.vma.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} km/h` : 'Non renseignée'}</strong></p>
            <p>FTP : <strong>{user.ftp != null ? `${user.ftp} W` : 'Non renseignée'}</strong></p>
            <button className={buttonClass} onClick={() => setShowStats(true)}>Modifier mes statistiques</button>
          </> : !userError && <p>Chargement du profil…</p>}
        </section>

        {user?.role === 'athlete' && <section className="space-y-4 rounded-3xl bg-white p-6 shadow-sm" aria-labelledby="ai-title">
          <h2 id="ai-title" className="text-xl font-black">Accès IA</h2>
          <a href="/guide-acces-ia.md" download="guide-acces-ia-coachtommy.md" className="inline-block font-bold text-brand-primary underline">Télécharger le guide d’intégration pour agents IA (.md)</a>
          <p>Cette clé permet à une application IA de consulter et modifier vos plans et séances, et de supprimer vos plans. La suppression d’un plan supprime aussi les séances qui lui sont liées.</p>
          <p>Ne divulguez cette clé qu’à une application de confiance : toute personne qui la possède peut accéder à vos données et agir en votre nom.</p>
          <p aria-live="polite">{aiActive === null ? (aiError ? 'État indisponible.' : 'Chargement de l’état…') : aiActive ? 'Clé active' : 'Aucune clé active'}</p>
          {aiError && <p role="alert" className="text-red-700">{aiError} {aiActive === null && <button className="underline" disabled={aiBusy} onClick={loadAiAccess}>Réessayer</button>}</p>}
          {aiActive !== null && <div className="flex flex-col gap-3 sm:flex-row">
            <button className={buttonClass} disabled={aiBusy} onClick={() => changeAiAccess(false)}>{aiBusy ? 'Veuillez patienter…' : aiActive ? 'Renouveler la clé' : 'Générer une clé'}</button>
            {aiActive && <button className={buttonClass} disabled={aiBusy} onClick={() => changeAiAccess(true)}>Révoquer la clé</button>}
          </div>}
          {aiKey && <div className="space-y-3 rounded-2xl bg-brand-surface p-4">
            <p>Cette clé ne sera affichée qu’une seule fois. Copiez-la maintenant et conservez-la en lieu sûr.</p>
            <label htmlFor="ai-key" className="font-bold">Votre clé API IA</label>
            <textarea id="ai-key" readOnly value={aiKey} rows={3} className="w-full rounded-xl border border-gray-400 p-3 break-all" />
            <div className="flex flex-col gap-3 sm:flex-row">
              <button className={buttonClass} onClick={copyAiKey}>Copier la clé</button>
              <button className={buttonClass} onClick={() => { setAiKey(''); setAiCopied(false); }}>Masquer la clé</button>
            </div>
            <p role="status">{aiCopied ? 'Clé copiée.' : ''}</p>
          </div>}
        </section>}

        <section className="space-y-4 rounded-3xl bg-white p-6 shadow-sm" aria-labelledby="garmin-title">
          <h2 id="garmin-title" className="flex items-center gap-2 text-xl font-black"><Watch className="h-5 w-5" /> Garmin</h2>
          {garminError ? <p role="alert" className="text-red-700">{garminError} <button className="underline" onClick={loadGarmin}>Réessayer</button></p> :
            <p>{garmin ? (garmin.is_connected ? `Connecté${garmin.garmin_email ? ` : ${garmin.garmin_email}` : ''}` : 'Non connecté') : 'Chargement…'}</p>}
          {garmin && <button className={buttonClass} onClick={() => setShowGarmin(true)}>Gérer Garmin</button>}
        </section>

        <section className="space-y-4 rounded-3xl bg-white p-6 shadow-sm" aria-labelledby="strava-title">
          <h2 id="strava-title" className="text-xl font-black">Strava</h2>
          <p>La synchronisation des activités Strava est indisponible et reportée.</p>
          <p>{strava ? (strava.connected ? 'Compte connecté' : 'Compte non connecté') : 'État indisponible'}</p>
          {stravaError && <p role="alert" className="text-red-700">{stravaError} {!strava && <button className="underline" onClick={loadStrava}>Réessayer</button>}</p>}
          {strava && <button className={buttonClass} disabled={stravaBusy} onClick={changeStrava}>{stravaBusy ? 'Veuillez patienter…' : strava.connected ? 'Déconnecter Strava' : 'Connecter Strava'}</button>}
          <p className="text-sm text-gray-600">Après autorisation, revenez sur cette page pour vérifier l’état de la connexion.</p>
        </section>

        <button className={`${buttonClass} inline-flex items-center justify-center gap-2`} onClick={() => { clearAuthToken(); router.push('/login'); }}><LogOut className="h-5 w-5" /> Se déconnecter</button>
      </div>
      <AthleteStatsModal isOpen={showStats} onClose={() => setShowStats(false)} onSuccess={loadUser} currentUser={user} />
      <GarminAuthModal isOpen={showGarmin} onClose={() => setShowGarmin(false)} onSuccess={loadGarmin} currentEmail={garmin?.garmin_email} isConnected={garmin?.is_connected ?? false} />
    </main>
  );
}
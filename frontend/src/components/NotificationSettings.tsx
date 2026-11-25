'use client';

import React, { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/api';
import { waitForActiveWorker } from '@/lib/notificationRegistration';

const buttonClass = 'w-full sm:w-auto rounded-2xl bg-brand-dark px-5 py-3 font-bold text-white hover:bg-brand-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-primary disabled:opacity-50';

async function request(path: string, options: RequestInit = {}) {
  const response = await fetchWithAuth(`/api/notifications${path}`, { ...options, cache: 'no-store' });
  if (!response.ok) throw new Error(`Opération impossible (erreur ${response.status}).`);
  return response.status === 204 ? null : response.json();
}

function publicKey(value: string) {
  if (!/^[A-Za-z0-9_-]+={0,2}$/.test(value)) throw new Error('Clé publique VAPID invalide.');
  const bytes = Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(value.length / 4) * 4, '=')), c => c.charCodeAt(0));
  if (bytes.length !== 65 || bytes[0] !== 4) throw new Error('Clé publique VAPID invalide.');
  return bytes;
}

export default function NotificationSettings() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [devices, setDevices] = useState<{ id: number }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [support, setSupport] = useState('');

  const load = async () => {
    try {
      const [preference, subscriptions] = await Promise.all([request('/preferences'), request('/subscriptions')]);
      setEnabled(preference.push_enabled);
      setDevices(subscriptions);
      setError('');
    } catch {
      setError('Impossible de charger les réglages de notifications.');
    }
  };

  useEffect(() => {
    if (!window.isSecureContext || !('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      setSupport('Notifications indisponibles : utilisez un navigateur compatible en HTTPS (ou localhost).');
    }
    void load();
  }, []);

  const subscribe = async (enableAccount = false) => {
    setBusy(true);
    setError('');
    setStatus('');
    try {
      const configuredKey = process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY;
      if (!configuredKey) throw new Error('La clé publique VAPID n’est pas configurée.');
      const key = publicKey(configuredKey);
      const permission = await Notification.requestPermission();
      if (permission === 'denied') throw new Error('Les notifications sont bloquées pour ce site. Autorisez-les dans les réglages du navigateur, puis réessayez.');
      if (permission !== 'granted') throw new Error('Autorisez les notifications dans la demande du navigateur pour continuer.');
      const registration = await navigator.serviceWorker.register('/notification-sw.js');
      await waitForActiveWorker(registration);
      const existing = await registration.pushManager.getSubscription();
      const existingKey = existing?.options.applicationServerKey;
      if (existingKey && (new Uint8Array(existingKey).length !== key.length || new Uint8Array(existingKey).some((byte, i) => byte !== key[i]))) {
        throw new Error('Cet appareil utilise une autre clé VAPID. Supprimez son abonnement dans les réglages du navigateur avant de le réinscrire.');
      }
      const subscription = existing || await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
      const data = subscription.toJSON();
      if (!data.endpoint || !data.keys?.p256dh || !data.keys?.auth) throw new Error('Abonnement incomplet.');
      await request('/subscriptions', { method: 'POST', body: JSON.stringify({ endpoint: data.endpoint, keys: { p256dh: data.keys.p256dh, auth: data.keys.auth } }) });
      if (enableAccount) {
        await request('/preferences', { method: 'PUT', body: JSON.stringify({ push_enabled: true }) });
      }
      setStatus(enableAccount ? 'Notifications activées et appareil enregistré.' : 'Appareil enregistré. Activez aussi la préférence générale pour recevoir les notifications.');
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible d’enregistrer cet appareil.');
    } finally {
      setBusy(false);
    }
  };

  const changePreference = async () => {
    setBusy(true);
    setError('');
    setStatus('');
    try {
      const result = await request('/preferences', { method: 'PUT', body: JSON.stringify({ push_enabled: !enabled }) });
      setEnabled(result.push_enabled);
      setStatus(result.push_enabled ? 'Notifications activées pour le compte.' : 'Notifications désactivées pour le compte.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de modifier la préférence.');
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    setBusy(true);
    setError('');
    setStatus('');
    try {
      await request(`/subscriptions/${id}`, { method: 'DELETE' });
      setDevices(current => current?.filter(device => device.id !== id) ?? null);
      setStatus('Appareil supprimé du compte. Il peut être réinscrit depuis son navigateur.');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible de supprimer cet appareil.');
    } finally {
      setBusy(false);
    }
  };

  return <section className="space-y-4 rounded-3xl bg-white p-6 shadow-sm" aria-labelledby="notifications-title">
    <h2 id="notifications-title" className="text-xl font-black">Notifications</h2>
    <p>Sur iPhone ou iPad, ajoutez l’application à l’écran d’accueil et ouvrez-la depuis celui-ci avant d’activer les notifications. Une version compatible d’iOS ou iPadOS est nécessaire.</p>
    {support && <p>{support}</p>}
    <p aria-live="polite">{enabled === null ? 'Préférence indisponible ou en cours de chargement.' : enabled ? 'Notifications activées pour le compte.' : 'Notifications désactivées pour le compte.'}</p>
    {error && <p role="alert" className="text-red-700">{error} <button type="button" className="underline" onClick={load}>Actualiser</button></p>}
    <p role="status">{status}</p>
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
      <button type="button" className={buttonClass} disabled={busy || enabled === null || (!enabled && !!support)} onClick={() => enabled ? changePreference() : subscribe(true)}>{enabled ? 'Désactiver les notifications' : 'Activer les notifications'}</button>
      <button type="button" className={buttonClass} disabled={busy || !!support} onClick={() => subscribe()}>Enregistrer cet appareil</button>
    </div>
    <h3 className="font-bold">Appareils enregistrés</h3>
    <p className="text-sm text-gray-600">Les appareils sont identifiés par un numéro. Leur suppression ne modifie pas la permission du navigateur.</p>
    {devices === null ? <p>Liste indisponible ou en cours de chargement.</p> : devices.length === 0 ? <p>Aucun appareil enregistré.</p> : <ul className="space-y-3">{devices.map(device => <li key={device.id} className="flex flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between"><span>Appareil n° {device.id}</span><button type="button" className={buttonClass} disabled={busy} onClick={() => remove(device.id)} aria-label={`Supprimer l’appareil n° ${device.id}`}>Supprimer</button></li>)}</ul>}
  </section>;
}
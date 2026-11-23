'use client';

import React, { useRef, useState } from 'react';
import Link from 'next/link';
import { Activity } from 'lucide-react';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const submitting = useRef(false);
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (submitting.current) return;
    setError('');
    if (password !== confirmation) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }
    submitting.current = true;
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      if (response.ok) {
        setPassword('');
        setConfirmation('');
        setSuccess(true);
      } else if (response.status === 409) {
        setError('Cette adresse email est déjà utilisée.');
      } else if (response.status === 422) {
        setError('Vérifiez votre adresse email et votre mot de passe : au moins 8 caractères et au maximum 72 octets UTF-8.');
      } else {
        setError('Impossible de créer le compte. Veuillez réessayer.');
      }
    } catch {
      setError('Erreur de connexion au serveur. Veuillez réessayer.');
    } finally {
      submitting.current = false;
      setLoading(false);
    }
  };

  const inputClass = 'block w-full px-5 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark shadow-inner';
  const labelClass = 'text-xs font-black uppercase tracking-widest text-brand-secondary mb-2 block ml-1';
  return (
    <main className="min-h-screen flex items-center justify-center bg-brand-surface p-4">
      <div className="max-w-md w-full space-y-6 bg-white p-6 sm:p-10 rounded-[2.5rem] shadow-2xl border border-brand-light">
        <div className="text-center">
          <div className="inline-flex bg-brand-dark p-4 rounded-2xl"><Activity className="w-10 h-10 text-white" /></div>
          <h1 className="mt-6 text-3xl font-black text-brand-dark">Créer un compte</h1>
          <p className="mt-2 text-sm text-brand-secondary">Créez votre compte athlète pour commencer.</p>
        </div>
        {success ? (
          <div role="status" className="space-y-4 text-center">
            <p>Votre compte a été créé. Vous pouvez maintenant vous connecter.</p>
            <Link href="/login" className="inline-block font-bold text-brand-primary underline">Se connecter</Link>
          </div>
        ) : (
          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && <div role="alert" className="bg-rose-50 text-rose-600 p-4 rounded-2xl text-sm font-bold border border-rose-100">{error}</div>}
            <div><label htmlFor="register-email" className={labelClass}>Email</label><input id="register-email" type="email" autoComplete="email" required className={inputClass} value={email} onChange={event => setEmail(event.target.value)} /></div>
            <div><label htmlFor="register-password" className={labelClass}>Mot de passe</label><input id="register-password" type="password" autoComplete="new-password" required minLength={8} aria-describedby="password-help" className={inputClass} value={password} onChange={event => setPassword(event.target.value)} /><p id="password-help" className="mt-2 text-xs text-brand-secondary">Au moins 8 caractères, au maximum 72 octets UTF-8.</p></div>
            <div><label htmlFor="register-confirmation" className={labelClass}>Confirmer le mot de passe</label><input id="register-confirmation" type="password" autoComplete="new-password" required className={inputClass} value={confirmation} onChange={event => setConfirmation(event.target.value)} /></div>
            <button type="submit" disabled={loading} className="w-full py-4 px-4 text-sm font-black rounded-2xl text-white bg-brand-primary hover:bg-brand-dark uppercase tracking-widest disabled:opacity-50">{loading ? 'Création en cours...' : 'Créer mon compte'}</button>
            <p className="text-center text-sm"><Link href="/login" className="font-bold text-brand-primary underline">Retour à la connexion</Link></p>
          </form>
        )}
      </div>
    </main>
  );
}
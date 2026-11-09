'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Activity } from 'lucide-react';
import { setAuthToken } from '@/lib/api';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setAuthToken(data.access_token);
        localStorage.setItem('user', JSON.stringify({
          id: data.id,
          email: data.email,
          role: data.role
        }));
        router.push('/');
      } else {
        const errData = await response.json();
        setError(errData.detail || 'Identifiants incorrects');
      }
    } catch (err) {
      setError('Erreur de connexion au serveur');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-surface p-4 relative overflow-hidden">
      <div className="absolute top-0 left-0 w-96 h-96 bg-brand-primary/5 rounded-full -translate-x-1/2 -translate-y-1/2" />
      <div className="absolute bottom-0 right-0 w-[500px] h-[500px] bg-brand-accent/5 rounded-full translate-x-1/4 translate-y-1/4" />
      
      <div className="max-w-md w-full space-y-8 bg-white p-10 rounded-[2.5rem] shadow-2xl border border-brand-light relative z-10">
        <div className="text-center">
          <div className="flex justify-center">
            <div className="bg-brand-dark p-4 rounded-2xl shadow-lg shadow-brand-dark/20">
              <Activity className="w-10 h-10 text-white" />
            </div>
          </div>
          <h2 className="mt-6 text-4xl font-black text-brand-dark tracking-tight uppercase">Coach Tommy</h2>
          <p className="mt-2 text-sm text-brand-secondary font-medium">Connectez-vous pour commencer l'entraînement.</p>
        </div>
        
        <form className="mt-8 space-y-6" onSubmit={handleLogin}>
          {error && (
            <div className="bg-rose-50 text-rose-600 p-4 rounded-2xl text-sm font-bold border border-rose-100">
              {error}
            </div>
          )}
          
          <div className="space-y-4">
            <div>
              <label className="text-xs font-black uppercase tracking-widest text-brand-secondary mb-2 block ml-1">Email</label>
              <input
                type="email"
                required
                className="block w-full px-5 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark shadow-inner"
                placeholder="tom.meallant@gmail.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-black uppercase tracking-widest text-brand-secondary mb-2 block ml-1">Mot de passe</label>
              <input
                type="password"
                required
                className="block w-full px-5 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark shadow-inner"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              className="group relative w-full flex justify-center py-5 px-4 border border-transparent text-sm font-black rounded-2xl text-white bg-brand-primary hover:bg-brand-dark focus:outline-none transition-all uppercase tracking-widest disabled:opacity-50 shadow-lg shadow-brand-primary/30"
            >
              {loading ? 'Connexion...' : 'Se connecter'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

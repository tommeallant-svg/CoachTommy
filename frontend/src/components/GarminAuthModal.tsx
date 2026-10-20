'use client';

import React, { useState, useEffect } from 'react';
import { Watch, X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

interface GarminAuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentEmail?: string;
  isConnected: boolean;
}

interface GarminStatus {
  is_connected: boolean;
  garmin_email?: string;
}

export default function GarminAuthModal({ 
  isOpen, 
  onClose, 
  onSuccess, 
  currentEmail = '',
  isConnected = false 
}: GarminAuthModalProps) {
  const [email, setEmail] = useState(currentEmail);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [status, setStatus] = useState<GarminStatus | null>(null);

  useEffect(() => {
    if (isOpen) {
      // Reset state when modal opens
      setEmail(currentEmail);
      setPassword('');
      setError(null);
      setIsLoading(false);
      
      // Check current status
      if (isConnected) {
        setStatus({ is_connected: true, garmin_email: currentEmail });
      }
    }
  }, [isOpen, currentEmail, isConnected]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/auth/garmin/login', {
        method: 'POST',
        body: JSON.stringify({ email, password })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Échec de la connexion à Garmin Connect');
      }

      setStatus({ is_connected: true, garmin_email: email });
      setPassword('');
      onSuccess();
      onClose();
      
    } catch (err: any) {
      setError(err.message || 'Une erreur est survenue lors de la connexion');
      setIsLoading(false);
    }
  };

  const handleLogout = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/auth/garmin/logout', {
        method: 'POST'
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || 'Échec de la déconnexion');
      }

      setStatus({ is_connected: false });
      setEmail('');
      setPassword('');
      onSuccess();
      
    } catch (err: any) {
      setError(err.message || 'Une erreur est survenue lors de la déconnexion');
    } finally {
      setIsLoading(false);
    }
  };

  const checkStatus = async () => {
    try {
      const response = await fetchWithAuth('/api/auth/garmin/status');

      if (response.ok) {
        const data: GarminStatus = await response.json();
        setStatus(data);
        if (data.garmin_email) {
          setEmail(data.garmin_email);
        }
      }
    } catch (err) {
      console.error('Failed to check Garmin status:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-[2.5rem] p-8 max-w-md w-full shadow-2xl border border-gray-100"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="bg-black p-2.5 rounded-xl">
              <Watch className="w-5 h-5 text-white" />
            </div>
            <h3 className="text-xl font-black uppercase tracking-tight">
              {status?.is_connected ? 'Gestion Garmin Connect' : 'Connexion à Garmin Connect'}
            </h3>
          </div>
          <button
            onClick={onClose}
            disabled={isLoading}
            className="p-2 text-gray-400 hover:text-black hover:bg-gray-100 rounded-xl transition-all disabled:opacity-50"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
            <span className="text-sm font-medium text-red-600">{error}</span>
          </div>
        )}

        {status?.is_connected ? (
          <div className="text-center space-y-6">
            <div className="w-16 h-16 mx-auto bg-green-500/20 rounded-full flex items-center justify-center border-2 border-green-500">
              <CheckCircle2 className="w-8 h-8 text-green-500" />
            </div>
            <h4 className="text-lg font-black uppercase tracking-tight">Connecté à Garmin Connect</h4>
            <p className="text-sm text-gray-500 font-medium">
              Compte: <span className="font-black text-black">{status.garmin_email}</span>
            </p>
            <div className="flex flex-col gap-3">
              <button
                onClick={handleLogout}
                disabled={isLoading}
                className="w-full bg-black text-white font-black uppercase text-xs tracking-widest py-4 rounded-2xl hover:bg-gray-800 transition-all disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Action en cours...
                  </>
                ) : (
                  'Déconnecter / Reconnecter'
                )}
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleLogin} className="space-y-4">
            <p className="text-sm text-gray-600 font-medium mb-4">
              Connectez-vous à votre compte Garmin Connect pour pouvoir envoyer vos séances directement vers votre montre Garmin.
            </p>
            
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">
                Adresse email Garmin
              </label>
              <input
                type="email"
                className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="votre@email.com"
                required
                disabled={isLoading}
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">
                Mot de passe
              </label>
              <input
                type="password"
                className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Votre mot de passe Garmin"
                required
                disabled={isLoading}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading || !email || !password}
              className="w-full bg-black text-white font-black uppercase text-xs tracking-widest py-4 rounded-2xl hover:bg-gray-800 transition-all disabled:opacity-50 flex items-center justify-center gap-2 mt-6"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Connexion en cours...
                </>
              ) : (
                'Se connecter à Garmin Connect'
              )}
            </button>
          </form>
        )}

        {!status?.is_connected && (
          <div className="mt-6 text-xs text-gray-400 font-medium leading-relaxed">
            <p><strong>Note:</strong> vos identifiants Garmin sont utilisés uniquement pour l'authentification et ne sont pas stockés sur nos serveurs. Seul le token d'accès est sauvegardé pour les envois futurs.</p>
          </div>
        )}
      </div>
    </div>
  );
}
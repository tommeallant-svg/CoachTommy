'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, 
  Activity, 
  Zap,
  Loader2,
  Info
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { User, UserUpdateStats } from '@/types/user';

interface AthleteStatsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentUser: User | null;
}

const AthleteStatsModal: React.FC<AthleteStatsModalProps> = ({ 
  isOpen, 
  onClose, 
  onSuccess,
  currentUser 
}) => {
  const [vma, setVma] = useState<string>('');
  const [ftp, setFtp] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (currentUser) {
      setVma(currentUser.vma ? currentUser.vma.toString() : '');
      setFtp(currentUser.ftp ? currentUser.ftp.toString() : '');
    }
  }, [currentUser, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/auth/me/stats', {
        method: 'PATCH',
        body: JSON.stringify({
          vma: vma ? parseFloat(vma) : null,
          ftp: ftp ? parseInt(ftp) : null,
        } as UserUpdateStats),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Une erreur est survenue');
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-white rounded-[2.5rem] w-full max-w-md overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-300">
        {/* Header */}
        <div className="bg-blue-600 p-8 text-white relative">
          <button 
            onClick={onClose}
            className="absolute top-6 right-6 p-2 hover:bg-white/20 rounded-full transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          
          <div className="flex items-center gap-4 mb-2">
            <div className="bg-white/20 p-3 rounded-2xl">
              <Activity className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-2xl font-black uppercase tracking-tighter">Profil Athlète</h2>
              <p className="text-blue-100 text-sm font-medium">Vos capacités physiologiques</p>
            </div>
          </div>
        </div>

        <div className="p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 mb-2 ml-1">
                VMA (km/h)
              </label>
              <div className="relative">
                <Activity className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="number"
                  step="0.1"
                  min="5"
                  max="30"
                  placeholder="Ex: 16.5"
                  value={vma}
                  onChange={(e) => setVma(e.target.value)}
                  className="w-full bg-gray-50 border-2 border-gray-50 px-12 py-4 rounded-2xl font-bold focus:bg-white focus:border-blue-600 transition-all outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 mb-2 ml-1">
                FTP (Watts)
              </label>
              <div className="relative">
                <Zap className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="number"
                  min="50"
                  max="600"
                  placeholder="Ex: 250"
                  value={ftp}
                  onChange={(e) => setFtp(e.target.value)}
                  className="w-full bg-gray-50 border-2 border-gray-50 px-12 py-4 rounded-2xl font-bold focus:bg-white focus:border-blue-600 transition-all outline-none"
                />
              </div>
            </div>

            {error && (
              <div className="p-4 bg-red-50 border border-red-100 rounded-2xl text-red-600 text-sm font-bold flex items-center gap-3">
                <Info className="w-5 h-5 shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-black text-white font-black uppercase text-xs tracking-widest py-5 rounded-2xl hover:bg-gray-800 transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-xl shadow-black/10"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Enregistrement...
                </>
              ) : (
                'Mettre à jour mes statistiques'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default AthleteStatsModal;

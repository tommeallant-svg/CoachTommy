'use client';

import React, { useState, useEffect } from 'react';
import { 
  X, 
  Calendar, 
  Clock, 
  Activity, 
  Loader2,
  Droplets,
  Info
} from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';
import { User, UserUpdateMenstrualCycle } from '@/types/user';

interface MenstrualCycleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  currentUser: User | null;
}

const MenstrualCycleModal: React.FC<MenstrualCycleModalProps> = ({ 
  isOpen, 
  onClose, 
  onSuccess,
  currentUser 
}) => {
  const [lastPeriodDate, setLastPeriodDate] = useState('');
  const [cycleLength, setCycleLength] = useState(28);
  const [periodLength, setPeriodLength] = useState(5);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (currentUser) {
      if (currentUser.last_period_date) {
        setLastPeriodDate(currentUser.last_period_date);
      }
      if (currentUser.cycle_length) {
        setCycleLength(currentUser.cycle_length);
      }
      if (currentUser.period_length) {
        setPeriodLength(currentUser.period_length);
      }
    }
  }, [currentUser, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetchWithAuth('/api/auth/me/menstrual-cycle', {
        method: 'PATCH',
        body: JSON.stringify({
          last_period_date: lastPeriodDate,
          cycle_length: cycleLength,
          period_length: periodLength,
        } as UserUpdateMenstrualCycle),
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

  const calculatePhase = () => {
    if (!lastPeriodDate) return null;
    
    const last = new Date(lastPeriodDate);
    const today = new Date();
    const diffTime = Math.abs(today.getTime() - last.getTime());
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) % cycleLength;
    
    if (diffDays <= periodLength) {
      return { name: 'Menstruation', color: 'text-red-500', bg: 'bg-red-50' };
    } else if (diffDays <= 13) {
      return { name: 'Phase Folliculaire', color: 'text-blue-500', bg: 'bg-blue-50' };
    } else if (diffDays <= 16) {
      return { name: 'Ovulation', color: 'text-purple-500', bg: 'bg-purple-50' };
    } else {
      return { name: 'Phase Lutéale', color: 'text-orange-500', bg: 'bg-orange-50' };
    }
  };

  const phase = calculatePhase();

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
      <div className="bg-white rounded-[2.5rem] w-full max-w-md overflow-hidden shadow-2xl animate-in fade-in zoom-in duration-300">
        {/* Header */}
        <div className="bg-red-500 p-8 text-white relative">
          <button 
            onClick={onClose}
            className="absolute top-6 right-6 p-2 hover:bg-white/20 rounded-full transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
          
          <div className="flex items-center gap-4 mb-2">
            <div className="bg-white/20 p-3 rounded-2xl">
              <Droplets className="w-8 h-8" />
            </div>
            <div>
              <h2 className="text-2xl font-black uppercase tracking-tighter">Cycle Menstruel</h2>
              <p className="text-red-100 text-sm font-medium">Suivi de votre santé et performance</p>
            </div>
          </div>
        </div>

        <div className="p-8">
          {phase && (
            <div className={`mb-8 p-4 rounded-2xl ${phase.bg} border border-current/10 flex items-center justify-between`}>
              <div className="flex items-center gap-3">
                <Activity className={`w-5 h-5 ${phase.color}`} />
                <span className={`font-black uppercase text-xs tracking-widest ${phase.color}`}>
                  Phase Actuelle
                </span>
              </div>
              <span className={`font-bold ${phase.color}`}>
                {phase.name}
              </span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 mb-2 ml-1">
                Dernier premier jour des règles
              </label>
              <div className="relative">
                <Calendar className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  type="date"
                  required
                  value={lastPeriodDate}
                  onChange={(e) => setLastPeriodDate(e.target.value)}
                  className="w-full bg-gray-50 border-2 border-gray-50 px-12 py-4 rounded-2xl font-bold focus:bg-white focus:border-red-500 transition-all outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 mb-2 ml-1">
                  Durée du cycle (jours)
                </label>
                <div className="relative">
                  <Clock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="number"
                    min="20"
                    max="45"
                    required
                    value={cycleLength}
                    onChange={(e) => setCycleLength(parseInt(e.target.value))}
                    className="w-full bg-gray-50 border-2 border-gray-50 px-12 py-4 rounded-2xl font-bold focus:bg-white focus:border-red-500 transition-all outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 mb-2 ml-1">
                  Durée des règles (jours)
                </label>
                <div className="relative">
                  <Droplets className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input
                    type="number"
                    min="1"
                    max="10"
                    required
                    value={periodLength}
                    onChange={(e) => setPeriodLength(parseInt(e.target.value))}
                    className="w-full bg-gray-50 border-2 border-gray-50 px-12 py-4 rounded-2xl font-bold focus:bg-white focus:border-red-500 transition-all outline-none"
                  />
                </div>
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
                'Mettre à jour mon cycle'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default MenstrualCycleModal;

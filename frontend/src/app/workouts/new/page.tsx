'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  Save, 
  Clock, 
  MapPin, 
  Dumbbell, 
  Star, 
  MessageSquare 
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/api';

const WORKOUT_TYPES = ['Libre', 'Endurance', 'Fractionné', 'Sortie Longue', 'Trail'];

export default function NewManualWorkoutPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    duration_minutes: 45,
    distance_km: 7.5,
    workout_type: 'Libre',
    perceived_difficulty: 5,
    athlete_comment: '',
    date: new Date().toISOString().slice(0, 16)
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetchWithAuth('/api/workouts/manual', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          date: format(new Date(formData.date), "yyyy-MM-dd'T'HH:mm:ss")
        })
      });
      if (res.ok) {
        router.push('/');
      } else {
        alert('Erreur lors de la création de la séance');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <div className="bg-white border-b border-gray-100 sticky top-0 z-30 px-6 py-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-gray-400 hover:text-black transition-colors font-black uppercase text-xs tracking-widest">
            <ChevronLeft className="w-5 h-5" />
            <span>Annuler</span>
          </Link>
          <h1 className="text-2xl font-black text-black uppercase tracking-tighter">Ajouter une séance</h1>
          <div className="w-20" />
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 mt-12">
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white p-8 rounded-[2.5rem] shadow-sm border border-gray-100 space-y-8">
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Date & Heure</label>
                <div className="relative">
                  <input
                    type="datetime-local"
                    className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                    value={formData.date}
                    onChange={e => setFormData({...formData, date: e.target.value})}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Type de séance</label>
                <select
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer"
                  value={formData.workout_type}
                  onChange={e => setFormData({...formData, workout_type: e.target.value})}
                >
                  {WORKOUT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Durée (min)</label>
                <div className="relative">
                  <Clock className="absolute left-6 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-300" />
                  <input
                    type="number"
                    step={['Libre', 'Sortie Longue', 'Sortie longue'].includes(formData.workout_type) ? 5 : 1}
                    className="w-full pl-14 pr-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                    value={formData.duration_minutes}
                    onChange={e => setFormData({...formData, duration_minutes: parseInt(e.target.value)})}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Distance (km)</label>
                <div className="relative">
                  <MapPin className="absolute left-6 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-300" />
                  <input
                    type="number"
                    step="0.01"
                    className="w-full pl-14 pr-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                    value={formData.distance_km}
                    onChange={e => setFormData({...formData, distance_km: parseFloat(e.target.value)})}
                  />
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Difficulté ressentie</label>
                <span className="text-sm font-black text-black">{formData.perceived_difficulty}/10</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                className="w-full h-2 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-black"
                value={formData.perceived_difficulty}
                onChange={e => setFormData({...formData, perceived_difficulty: parseInt(e.target.value)})}
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Commentaire</label>
              <textarea
                className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold text-sm min-h-[120px]"
                placeholder="Comment s'est passée votre séance ?"
                value={formData.athlete_comment}
                onChange={e => setFormData({...formData, athlete_comment: e.target.value})}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-6 rounded-[2rem] bg-black text-white font-black uppercase tracking-[0.3em] hover:bg-gray-800 transition-all shadow-xl shadow-gray-200 disabled:opacity-50"
          >
            {loading ? 'Enregistrement...' : 'Valider la séance'}
          </button>
        </form>
      </div>
    </div>
  );
}

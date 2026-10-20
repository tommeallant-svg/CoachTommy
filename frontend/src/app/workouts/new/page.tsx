'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { 
  ChevronLeft, 
  Save, 
  Clock, 
  MapPin, 
  Dumbbell, 
  Star, 
  Zap,
  RotateCcw,
  BookOpen,
  X,
  Loader2,
  Users
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';
import { fetchWithAuth, getAuthUser } from '@/lib/api';

const WORKOUT_TYPES = ['Libre', 'Endurance', 'Fractionné', 'Sortie Longue', 'Trail'];

function NewManualWorkoutPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const athleteIdParam = searchParams.get('athleteId');
  
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<any>(null);
  const [athletes, setAthletes] = useState<any[]>([]);
  const [showCatalogModal, setShowCatalogModal] = useState(false);
  const [catalogWorkouts, setCatalogWorkouts] = useState<any[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [athleteVma, setAthleteVma] = useState<number | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    duration_minutes: 45,
    distance_km: 7.5,
    workout_type: 'Libre',
    difficulty_level: 5,
    perceived_difficulty: 5,
    athlete_comment: '',
    date: new Date().toISOString().slice(0, 16),
    athlete_id: athleteIdParam ? parseInt(athleteIdParam) : null,
    description: '',
    scheme: [] as any[]
  });

  useEffect(() => {
    const authUser = getAuthUser();
    setUser(authUser);
    
    if (authUser?.role === 'coach') {
      fetchAthletes();
    }
  }, []);

  useEffect(() => {
    if (formData.athlete_id) {
      fetchAthleteVma(formData.athlete_id);
    } else {
      setAthleteVma(null);
    }
  }, [formData.athlete_id]);

  const fetchAthleteVma = async (athleteId: number) => {
    try {
      const res = await fetchWithAuth(`/api/plans/current?athlete_id=${athleteId}`);
      if (res.ok) {
        const data = await res.json();
        if (data && data.estimated_vma) {
          setAthleteVma(data.estimated_vma);
        }
      }
    } catch (err) {
      console.error('Erreur lors de la récupération de la VMA:', err);
    }
  };

  const fetchAthletes = async () => {
    try {
      const res = await fetchWithAuth('/api/coach/athletes');
      if (res.ok) {
        const data = await res.json();
        setAthletes(data);
      }
    } catch (err) {
      console.error('Erreur lors de la récupération des athlètes:', err);
    }
  };

  const fetchCatalog = async () => {
    setLoadingCatalog(true);
    try {
      const response = await fetchWithAuth('/api/catalog');
      if (response.ok) {
        const data = await response.json();
        setCatalogWorkouts(data);
      }
    } catch (error) {
      console.error('Error fetching catalog:', error);
    } finally {
      setLoadingCatalog(false);
    }
  };

  const formatMinutesToMMSS = (minutes: number): string => {
    const totalSeconds = Math.floor(minutes * 60);
    const mm = Math.floor(totalSeconds / 60);
    const ss = totalSeconds % 60;
    return `${mm}:${ss.toString().padStart(2, '0')}`;
  };

  const convertVmaPercentageToPace = (vmaMinKm: number, percentage: number): string => {
    if (percentage <= 0) return "0:00";
    const paceMinKm = vmaMinKm / (percentage / 100);
    return formatMinutesToMMSS(paceMinKm);
  };

  const handleSelectFromCatalog = async (catalogWorkout: any) => {
    const scheme = catalogWorkout.scheme || [];
    let totalDuration = 0;
    const processedScheme = scheme.map((block: any) => {
      const repetitions = block.repetitions || 1;
      const processedIntervals = block.intervals?.map((interval: any) => {
        if (interval.pace_vma_min !== undefined && interval.pace_vma_max !== undefined && athleteVma) {
          return {
            ...interval,
            pace_min: convertVmaPercentageToPace(athleteVma, interval.pace_vma_min),
            pace_max: convertVmaPercentageToPace(athleteVma, interval.pace_vma_max)
          };
        }
        return interval;
      });
      if (processedIntervals) {
        processedIntervals.forEach((interval: any) => {
          if (interval.duration) {
            totalDuration += interval.duration * repetitions;
          }
        });
      }
      return { ...block, intervals: processedIntervals };
    });

    setFormData({
      ...formData,
      name: catalogWorkout.name,
      workout_type: catalogWorkout.workout_type,
      duration_minutes: Math.round(totalDuration),
      difficulty_level: catalogWorkout.perceived_difficulty || 5,
      perceived_difficulty: catalogWorkout.perceived_difficulty || 5,
      description: catalogWorkout.description || '',
      scheme: processedScheme
    });
    setShowCatalogModal(false);
  };

  const handleOpenCatalog = async () => {
    if (!formData.athlete_id && user?.role === 'coach') {
      alert("Veuillez d'abord sélectionner un athlète pour adapter les allures du catalogue à sa VMA.");
      return;
    }
    if (catalogWorkouts.length === 0) {
      await fetchCatalog();
    }
    setShowCatalogModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const endpoint = formData.scheme && formData.scheme.length > 0 ? '/api/workouts' : '/api/workouts/manual';
      const res = await fetchWithAuth(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          date: format(new Date(formData.date), "yyyy-MM-dd'T'HH:mm:ss")
        })
      });
      if (res.ok) {
        const backUrl = formData.athlete_id ? `/?athleteId=${formData.athlete_id}` : '/';
        router.push(backUrl);
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
          <Link href={athleteIdParam ? `/?athleteId=${athleteIdParam}` : "/"} className="flex items-center gap-2 text-gray-400 hover:text-black transition-colors font-black uppercase text-xs tracking-widest">
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
            
            {/* Coach-only athlete selector */}
            {user?.role === 'coach' && (
              <div className="space-y-4 pb-6 border-b border-gray-50">
                <div className="flex items-center justify-between">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1 flex items-center gap-2">
                    <Users className="w-3 h-3" />
                    Attribuer à l'athlète
                  </label>
                  <button
                    type="button"
                    onClick={handleOpenCatalog}
                    className="flex items-center gap-2 bg-gray-50 text-black border border-gray-100 px-4 py-2 rounded-xl font-black uppercase text-[9px] tracking-widest hover:bg-black hover:text-white transition-all shadow-sm"
                  >
                    <BookOpen className="w-3 h-3" />
                    Piocher dans le catalogue
                  </button>
                </div>
                <select
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer"
                  value={formData.athlete_id || ''}
                  onChange={e => setFormData({...formData, athlete_id: e.target.value ? parseInt(e.target.value) : null})}
                  required
                >
                  <option value="">Choisir un athlète...</option>
                  {athletes.map(a => (
                    <option key={a.id} value={a.id}>{a.email}</option>
                  ))}
                </select>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Nom de la séance</label>
              <input
                type="text"
                placeholder={user?.role === 'coach' ? "Ex: Séance de VMA, Footing..." : "Séance manuelle"}
                className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                value={formData.name}
                onChange={e => setFormData({...formData, name: e.target.value})}
              />
            </div>

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
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">
                  {user?.role === 'coach' ? 'Intensité prévue' : 'Difficulté ressentie'}
                </label>
                <span className="text-sm font-black text-black">
                  {user?.role === 'coach' ? formData.difficulty_level : formData.perceived_difficulty}/10
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                className="w-full h-2 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-black"
                value={user?.role === 'coach' ? formData.difficulty_level : formData.perceived_difficulty}
                onChange={e => {
                  const val = parseInt(e.target.value);
                  if (user?.role === 'coach') {
                    setFormData({...formData, difficulty_level: val, perceived_difficulty: val});
                  } else {
                    setFormData({...formData, perceived_difficulty: val});
                  }
                }}
              />
            </div>

            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">
                {user?.role === 'coach' ? 'Consignes / Description' : 'Commentaire'}
              </label>
              <textarea
                className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold text-sm min-h-[120px]"
                placeholder={user?.role === 'coach' ? "Détaillez la séance pour votre athlète..." : "Comment s'est passée votre séance ?"}
                value={user?.role === 'coach' ? formData.description : formData.athlete_comment}
                onChange={e => {
                  if (user?.role === 'coach') {
                    setFormData({...formData, description: e.target.value});
                  } else {
                    setFormData({...formData, athlete_comment: e.target.value});
                  }
                }}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-6 rounded-[2rem] bg-black text-white font-black uppercase tracking-[0.3em] hover:bg-gray-800 transition-all shadow-xl shadow-gray-200 disabled:opacity-50"
          >
            {loading ? 'Enregistrement...' : (user?.role === 'coach' ? 'Programmer la séance' : 'Valider la séance')}
          </button>
        </form>
      </div>

      {/* Catalog Modal */}
      {showCatalogModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowCatalogModal(false)}
        >
          <div
            className="bg-white rounded-[2.5rem] p-8 max-w-2xl w-full shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="bg-yellow-400 p-2 rounded-xl">
                  <BookOpen className="w-5 h-5 text-black" />
                </div>
                <div>
                  <h3 className="text-xl font-black uppercase tracking-tight">Catalogue</h3>
                  {athleteVma && (
                    <p className="text-sm text-gray-500 font-medium mt-1">VMA de l'athlète : <span className="font-black text-black">{formatMinutesToMMSS(athleteVma)}/km</span></p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setShowCatalogModal(false)}
                className="p-2 text-gray-400 hover:text-black hover:bg-gray-100 rounded-xl transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {loadingCatalog ? (
              <div className="text-center py-12 font-bold text-gray-400">Chargement...</div>
            ) : catalogWorkouts.length === 0 ? (
              <div className="text-center py-12 font-bold text-gray-400">Catalogue vide</div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {catalogWorkouts.map((catalogWorkout) => (
                  <button
                    key={catalogWorkout.id}
                    onClick={() => handleSelectFromCatalog(catalogWorkout)}
                    className="w-full bg-gray-50 hover:bg-black hover:text-white border border-gray-100 rounded-2xl p-6 text-left transition-all group"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-lg font-black uppercase tracking-tight group-hover:text-yellow-400">{catalogWorkout.name}</h4>
                        <div className="flex items-center gap-4 mt-2 text-sm font-medium text-gray-500 group-hover:text-gray-300">
                          <span className="text-[10px] font-black uppercase tracking-widest">{catalogWorkout.workout_type}</span>
                          <span className="text-[10px] font-black uppercase tracking-widest">Difficulté : {catalogWorkout.perceived_difficulty}/10</span>
                        </div>
                      </div>
                      <ChevronLeft className="w-5 h-5 transform rotate-180 text-gray-400 group-hover:text-white" />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function NewManualWorkoutPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center font-black uppercase tracking-widest text-gray-400">Chargement...</div>}>
      <NewManualWorkoutPageContent />
    </Suspense>
  );
}

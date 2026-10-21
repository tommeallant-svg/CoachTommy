'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  BookOpen, 
  Plus, 
  Pencil, 
  Trash2, 
  Save,
  X,
  Dumbbell,
  Activity,
  Tag,
  Calendar
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth, getAuthUser } from '@/lib/api';

export default function CatalogPage() {
  const router = useRouter();
  const [workouts, setWorkouts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<any>(null);
  const [assigningWorkout, setAssigningWorkout] = useState<any>(null);
  const [athletes, setAthletes] = useState<any[]>([]);
  const [selectedAthleteId, setSelectedAthleteId] = useState<number | null>(null);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().slice(0, 16));
  const [isAssigning, setIsAssigning] = useState(false);

  useEffect(() => {
    const user = getAuthUser();
    if (user?.role !== 'coach') {
      router.push('/');
      return;
    }
    fetchCatalog();
    fetchAthletes();
  }, [router]);

  const fetchAthletes = async () => {
    try {
      const res = await fetchWithAuth('/api/coach/athletes');
      if (res.ok) {
        const data = await res.json();
        setAthletes(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchCatalog = async () => {
    try {
      const res = await fetchWithAuth('/api/catalog');
      if (res.ok) {
        const data = await res.json();
        setWorkouts(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Voulez-vous vraiment supprimer cet entraînement du catalogue ?')) return;
    try {
      const res = await fetchWithAuth(`/api/catalog/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setWorkouts(workouts.filter(w => w.id !== id));
      }
    } catch (err) {
      console.error(err);
    }
  };

  const startEditing = (workout: any) => {
    setEditingId(workout.id);
    setEditForm({
      name: workout.name,
      workout_type: workout.workout_type,
      perceived_difficulty: workout.perceived_difficulty
    });
  };

  const handleQuickSave = async (id: number) => {
    try {
      const res = await fetchWithAuth(`/api/catalog/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(editForm)
      });
      if (res.ok) {
        const updated = await res.json();
        setWorkouts(workouts.map(w => w.id === id ? updated : w));
        setEditingId(null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleAssign = async () => {
    if (!selectedAthleteId || !assigningWorkout) return;
    setIsAssigning(true);
    try {
      // Trouver l'athlète sélectionné dans la liste pour avoir sa VMA et FTP
      const athlete = athletes.find(a => a.id === selectedAthleteId);
      const athleteVma = athlete?.vma || 15.0; // km/h par défaut si non renseigné
      const athleteFtp = athlete?.ftp || 200; // Watts par défaut si non renseigné

      // Préparer la séance
      const formatMinutesToMMSS = (minutes: number): string => {
        const totalSeconds = Math.floor(minutes * 60);
        const mm = Math.floor(totalSeconds / 60);
        const ss = totalSeconds % 60;
        return `${mm}:${ss.toString().padStart(2, '0')}`;
      };

      const convertVmaPercentageToPace = (vmaKmH: number, percentage: number): string => {
        if (percentage <= 0) return "0:00";
        // VMA est en km/h. On veut l'allure en min/km.
        // allure (min/km) = 60 / vitesse (km/h)
        const speedKmH = vmaKmH * (percentage / 100);
        const paceMinKm = 60 / speedKmH;
        return formatMinutesToMMSS(paceMinKm);
      };

      const convertFtpPercentageToWatts = (ftp: number, percentage: number): number => {
        return Math.round(ftp * (percentage / 100));
      };

      const scheme = assigningWorkout.scheme || [];
      const isCycling = assigningWorkout.sport === 'cycling';
      let totalDuration = 0;

      const processedScheme = scheme.map((block: any) => {
        const repetitions = block.repetitions || 1;
        const processedIntervals = block.intervals?.map((interval: any) => {
          const newInterval = { ...interval };

          if (isCycling) {
            if (interval.power_ftp_min !== undefined) {
              newInterval.power_watt_min = convertFtpPercentageToWatts(athleteFtp, interval.power_ftp_min);
            }
            if (interval.power_ftp_max !== undefined) {
              newInterval.power_watt_max = convertFtpPercentageToWatts(athleteFtp, interval.power_ftp_max);
            }
          } else {
            if (interval.pace_vma_min !== undefined) {
              newInterval.pace_min = convertVmaPercentageToPace(athleteVma, interval.pace_vma_min);
            }
            if (interval.pace_vma_max !== undefined) {
              newInterval.pace_max = convertVmaPercentageToPace(athleteVma, interval.pace_vma_max);
            }
          }
          return newInterval;
        });

        if (processedIntervals) {
          processedIntervals.forEach((interval: any) => {
            if (interval.duration) totalDuration += interval.duration * repetitions;
          });
        }
        return { ...block, intervals: processedIntervals };
      });

      const res = await fetchWithAuth('/api/workouts', {
        method: 'POST',
        body: JSON.stringify({
          sport: assigningWorkout.sport || 'running',
          name: assigningWorkout.name,
          workout_type: assigningWorkout.workout_type,
          category: assigningWorkout.category,
          duration_minutes: Math.round(totalDuration),
          difficulty_level: assigningWorkout.perceived_difficulty || 5,
          description: assigningWorkout.description || assigningWorkout.name,
          date: new Date(selectedDate).toISOString(),
          athlete_id: selectedAthleteId,
          scheme: processedScheme
        })
      });

      if (res.ok) {
        alert('Séance assignée avec succès !');
        setAssigningWorkout(null);
      } else {
        alert('Erreur lors de l\'assignation');
      }
    } catch (err) {
      console.error(err);
      alert('Erreur réseau');
    } finally {
      setIsAssigning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <div className="bg-white border-b border-gray-100 sticky top-0 z-30 px-6 py-6">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/coach" className="flex items-center gap-2 text-gray-400 hover:text-black transition-colors font-black uppercase text-xs tracking-widest">
            <ChevronLeft className="w-5 h-5" />
            <span>Espace Entraîneur</span>
          </Link>
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-black text-black uppercase tracking-tighter">Catalogue</h1>
          </div>
          <div className="flex gap-4">
            <Link href="/catalog/new" className="flex items-center gap-2 bg-black text-white px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-800 transition-all">
              <Plus className="w-4 h-4" />
              <span>Créer</span>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 mt-12 space-y-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-black p-3 rounded-2xl">
              <BookOpen className="w-6 h-6 text-white" />
            </div>
            <h2 className="text-2xl font-black text-black uppercase tracking-tight">Entraînements Fractionnés</h2>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 font-black uppercase text-gray-400 tracking-widest">Chargement...</div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {workouts.map(workout => (
              <div key={workout.id} className="bg-white rounded-[2rem] p-6 shadow-sm border border-gray-100 transition-all hover:shadow-md">
                {editingId === workout.id ? (
                  <div className="flex flex-col md:flex-row items-center gap-6">
                    <div className="flex-1 w-full space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Nom de la séance</label>
                      <input 
                        type="text" 
                        value={editForm.name} 
                        onChange={e => setEditForm({...editForm, name: e.target.value})}
                        className="w-full bg-gray-50 border-none rounded-xl px-4 py-3 font-bold text-black focus:ring-2 focus:ring-black outline-none"
                      />
                    </div>
                    <div className="w-full md:w-48 space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Type</label>
                      <input 
                        type="text" 
                        value={editForm.workout_type} 
                        onChange={e => setEditForm({...editForm, workout_type: e.target.value})}
                        className="w-full bg-gray-50 border-none rounded-xl px-4 py-3 font-bold text-black focus:ring-2 focus:ring-black outline-none"
                      />
                    </div>
                    <div className="w-full md:w-32 space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Difficulté</label>
                      <input 
                        type="number" 
                        min="1" max="10"
                        value={editForm.perceived_difficulty} 
                        onChange={e => setEditForm({...editForm, perceived_difficulty: parseInt(e.target.value)})}
                        className="w-full bg-gray-50 border-none rounded-xl px-4 py-3 font-bold text-black focus:ring-2 focus:ring-black outline-none"
                      />
                    </div>
                    <div className="flex gap-2 pt-6">
                      <button onClick={() => handleQuickSave(workout.id)} className="p-4 bg-green-500 text-white rounded-2xl hover:bg-green-600 transition-all shadow-lg shadow-green-100">
                        <Save className="w-5 h-5" />
                      </button>
                      <button onClick={() => setEditingId(null)} className="p-4 bg-gray-100 text-gray-400 rounded-2xl hover:bg-gray-200 transition-all">
                        <X className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                    <div className="flex items-center gap-6 flex-1">
                      <div className="w-12 h-12 bg-gray-50 rounded-2xl flex items-center justify-center">
                        <Dumbbell className="w-6 h-6 text-black" />
                      </div>
                      <div>
                        <h3 className="text-xl font-black text-black uppercase tracking-tight">{workout.name}</h3>
                        <div className="flex items-center gap-4 mt-1">
                          <span className="flex items-center gap-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">
                            <Tag className="w-3 h-3" /> {workout.workout_type}
                          </span>
                          <span className="flex items-center gap-1 text-[10px] font-black text-gray-400 uppercase tracking-widest">
                            <Activity className="w-3 h-3" /> Difficulté : {workout.perceived_difficulty}/10
                          </span>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button 
                        onClick={() => setAssigningWorkout(workout)} 
                        className="p-4 bg-blue-50 text-blue-600 hover:text-white hover:bg-blue-600 rounded-2xl transition-all"
                        title="Assigner à un athlète"
                      >
                        <Calendar className="w-5 h-5" />
                      </button>
                      <button onClick={() => startEditing(workout)} className="p-4 bg-gray-50 text-gray-400 hover:text-black hover:bg-gray-100 rounded-2xl transition-all">
                        <Pencil className="w-5 h-5" />
                      </button>
                      <Link href={`/catalog/${workout.id}`} className="p-4 bg-gray-50 text-gray-400 hover:text-black hover:bg-gray-100 rounded-2xl transition-all">
                        <BookOpen className="w-5 h-5" />
                      </Link>
                      <button onClick={() => handleDelete(workout.id)} className="p-4 bg-red-50 text-red-400 hover:text-red-600 hover:bg-red-100 rounded-2xl transition-all">
                        <Trash2 className="w-5 h-5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
            {workouts.length === 0 && (
              <div className="text-center py-20 bg-white rounded-[2rem] border-2 border-dashed border-gray-100">
                <p className="font-black uppercase text-gray-300 tracking-[0.2em]">Le catalogue est vide</p>
                <Link href="/catalog/new" className="inline-block mt-6 text-sm font-black text-black underline underline-offset-8 decoration-2 hover:text-gray-600 transition-all">
                  Créer votre premier entraînement
                </Link>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Assignment Modal */}
      {assigningWorkout && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-[2.5rem] p-8 max-w-md w-full shadow-2xl border border-gray-100">
            <h3 className="text-xl font-black uppercase tracking-tight mb-6">Assigner : {assigningWorkout.name}</h3>
            
            <div className="space-y-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-gray-400 ml-1">Choisir l'athlète</label>
                <select
                  className="w-full bg-gray-50 border-none rounded-2xl px-6 py-4 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all appearance-none cursor-pointer"
                  value={selectedAthleteId || ''}
                  onChange={e => setSelectedAthleteId(parseInt(e.target.value))}
                >
                  <option value="">Sélectionner un athlète...</option>
                  {athletes.map(a => (
                    <option key={a.id} value={a.id}>{a.email}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-widest text-gray-400 ml-1">Date & Heure</label>
                <input
                  type="datetime-local"
                  className="w-full bg-gray-50 border-none rounded-2xl px-6 py-4 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
                  value={selectedDate}
                  onChange={e => setSelectedDate(e.target.value)}
                />
              </div>

              <div className="flex gap-4 pt-4">
                <button
                  onClick={() => setAssigningWorkout(null)}
                  className="flex-1 py-4 bg-gray-100 text-gray-500 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-200 transition-all"
                >
                  Annuler
                </button>
                <button
                  onClick={handleAssign}
                  disabled={!selectedAthleteId || isAssigning}
                  className="flex-1 py-4 bg-black text-white rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-800 transition-all shadow-lg disabled:opacity-50"
                >
                  {isAssigning ? 'Assignation...' : 'Assigner'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

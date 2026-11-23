'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  Clock, 
  AlignLeft, 
  Activity, 
  CheckCircle2, 
  Send,
  Calendar,
  RotateCcw,
  Dumbbell,
  Watch,
  BookOpen,
  X,
  Link2,
  Unlink,
  Loader2,
  Users,
  RefreshCw
} from 'lucide-react';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import Link from 'next/link';
import { Workout, WorkoutInterval, WorkoutBlock } from '@/types/workout';
import { fetchWithAuth, getAuthUser } from '@/lib/api';
import { Save, Edit2, Trash2 } from 'lucide-react';
import GarminAuthModal from '@/components/GarminAuthModal';
import { createCalendarEvent, createGoogleCalendarUrl, createIcsCalendar } from '@/lib/calendarExport';

// Fonction utilitaire pour convertir les minutes en format mm:ss
const formatMinutesToMMSS = (minutes: number): string => {
  const totalSeconds = Math.floor(minutes * 60);
  const mm = Math.floor(totalSeconds / 60);
  const ss = totalSeconds % 60;
  return `${mm}:${ss.toString().padStart(2, '0')}`;
};

// Convertir %VMA en allure réelle (mm:ss) en fonction de la VMA de l'athlète
// VMA est maintenant stockée en km/h dans le profil
const convertVmaPercentageToPace = (vmaKmH: number, percentage: number): string => {
  if (percentage <= 0) return "0:00";
  const speedKmH = vmaKmH * (percentage / 100);
  const paceMinKm = 60 / speedKmH;
  return formatMinutesToMMSS(paceMinKm);
};

export default function WorkoutDetailPage() {
  const { id } = useParams();
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const isCoach = user?.role === 'coach';

  const [workout, setWorkout] = useState<Workout | null>(null);
  const [loading, setLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [perceivedDifficulty, setPerceivedDifficulty] = useState(5);
  const [comment, setComment] = useState('');
  const [isValidating, setIsValidating] = useState(false);
  const [athletes, setAthletes] = useState<any[]>([]);

  const [editFormData, setEditFormData] = useState({
    name: '',
    sport: 'running' as 'running' | 'cycling',
    workout_type: '',
    duration_minutes: 0,
    difficulty_level: 0,
    description: '',
    date: '',
    scheme: [] as any[],
    athlete_id: null as number | null
  });
  const [showGarminHelp, setShowGarminHelp] = useState(false);
  const [showCatalogModal, setShowCatalogModal] = useState(false);
  const [catalogWorkouts, setCatalogWorkouts] = useState<any[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [athleteVma, setAthleteVma] = useState<number | null>(null);
  const [athleteFtp, setAthleteFtp] = useState<number | null>(null);
  const [catalogAthleteId, setCatalogAthleteId] = useState<number | null>(null);
  const [showGarminAuthModal, setShowGarminAuthModal] = useState(false);
  const [garminConnected, setGarminConnected] = useState(false);
  const [garminEmail, setGarminEmail] = useState<string | null>(null);
  const [isCheckingGarmin, setIsCheckingGarmin] = useState(false);
  const [pushError, setPushError] = useState<string | null>(null);
  const [pushSuccess, setPushSuccess] = useState(false);
  const [showCalendar, setShowCalendar] = useState(false);
  const [calendarDuration, setCalendarDuration] = useState('');
  
  useEffect(() => {
    const authUser = getAuthUser();
    setUser(authUser);

    if (authUser && !authUser.id) {
      fetchWithAuth('/api/auth/me')
        .then(res => res.json())
        .then(data => {
          const updatedUser = { ...authUser, id: data.id };
          localStorage.setItem('user', JSON.stringify(updatedUser));
          setUser(updatedUser);
        })
        .catch(err => console.error("Erreur récup user:", err));
    }

    fetchWorkout();
    checkGarminStatus();
    if (authUser?.role === 'coach') {
      fetchAthletes();
    }
  }, [id]);

  useEffect(() => {
    let active = true;
    setAthleteVma(null);
    setAthleteFtp(null);
    if (!user || !editFormData.athlete_id) return () => { active = false; };
    if (user.role === 'coach' && editFormData.athlete_id !== user.id) {
      const athlete = athletes.find(a => a.id === editFormData.athlete_id);
      if (athlete) {
        setAthleteVma(athlete.vma);
        setAthleteFtp(athlete.ftp);
      }
    } else {
      fetchWithAuth('/api/auth/me').then(res => res.ok ? res.json() : null).then(data => {
        if (active && data) {
          setAthleteVma(data.vma);
          setAthleteFtp(data.ftp);
        }
      }).catch(err => console.error('Erreur lors de la récupération des statistiques:', err));
    }
    return () => { active = false; };
  }, [editFormData.athlete_id, athletes, user]);

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

  const checkGarminStatus = async () => {
    setIsCheckingGarmin(true);
    try {
      const response = await fetchWithAuth('/api/auth/garmin/status');
      if (response.ok) {
        const data = await response.json();
        setGarminConnected(data.is_connected);
        setGarminEmail(data.garmin_email || null);
      }
    } catch (err) {
      console.error('Failed to check Garmin status:', err);
    } finally {
      setIsCheckingGarmin(false);
    }
  };

  const handleGarminExport = async () => {
     try {
       const res = await fetchWithAuth(`/api/workouts/${id}/garmin`);
       if (!res.ok) {
         const err = await res.json().catch(() => null);
         alert(err?.detail || 'Échec de l\'export Garmin');
         return;
       }
       const blob = await res.blob();
       const url = URL.createObjectURL(blob);
       const a = document.createElement('a');
       a.href = url;
       const safeName = (workout?.name || 'seance').replace(/[^A-Za-z0-9_.-]+/g, '_');
       a.download = `${safeName}.fit`;
       document.body.appendChild(a);
       a.click();
       a.remove();
       URL.revokeObjectURL(url);
       setShowGarminHelp(true);
     } catch (e) {
          console.error('Garmin export failed:', e);
       alert("Erreur réseau lors de l'export Garmin");
     }
   };

  const handlePushGarmin = async () => {
    // Check if connected to Garmin first
    if (!garminConnected) {
      setShowGarminAuthModal(true);
      return;
    }

    setPushError(null);
    setPushSuccess(false);
    
    try {
      setIsCheckingGarmin(true);
      const response = await fetchWithAuth(
        `/api/auth/garmin/sync-workout/${id}`,
        {
          method: "POST",
        }
      );
      
      if (!response.ok) {
        const err = await response.json().catch(() => null);
        setPushError(err?.detail || 'Impossible d\'envoyer la séance vers Garmin');
        return;
      }
      
      setPushSuccess(true);
      setTimeout(() => setPushSuccess(false), 5000);
      
    } catch (err) {
      setPushError('Erreur réseau lors de l\'envoi vers Garmin');
      console.error('Garmin push failed:', err);
    } finally {
      setIsCheckingGarmin(false);
    }
  };

  const handleGarminAuthSuccess = () => {
    // Refresh Garmin connection status after successful auth
    checkGarminStatus();
  };

  const fetchWorkout = async () => {
    try {
      const response = await fetchWithAuth(`/api/workouts/${id}`);
      if (!response.ok) throw new Error('Workout not found');
      const data = await response.json();
      setWorkout(data);
      if (data.is_validated) {
        setPerceivedDifficulty(data.perceived_difficulty || 5);
        setComment(data.athlete_comment || '');
      }
      setEditFormData({
        name: data.name,
        sport: data.sport || 'running',
        workout_type: data.workout_type,
        duration_minutes: data.duration_minutes,
        difficulty_level: data.difficulty_level,
        description: data.description || '',
        date: data.date.slice(0, 16),
        scheme: data.scheme || [],
        athlete_id: data.athlete_id
      });
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
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

  const handleSelectFromCatalog = async (catalogWorkout: any) => {
    // Convertir le scheme du catalogue au format workout avec les stats de l'athlète
    const scheme = catalogWorkout.scheme || [];
    const isCycling = catalogWorkout.sport === 'cycling';
    if ((isCycling && (!athleteFtp || athleteFtp <= 0)) || (!isCycling && (!athleteVma || athleteVma <= 0))) {
      alert("Les statistiques de l'athlète sont indisponibles. Renseignez sa VMA ou sa FTP avant de sélectionner une séance.");
      return;
    }
    
    // Calculer la durée totale estimée et convertir les % en valeurs réelles
    let totalDuration = 0;
    const processedScheme = scheme.map((block: any) => {
      const repetitions = block.repetitions || 1;
      const processedIntervals = block.intervals?.map((interval: any) => {
        const newInterval = { ...interval };
        
        if (isCycling && athleteFtp) {
          if (interval.power_ftp_min !== undefined) {
            newInterval.power_watt_min = Math.round(athleteFtp * (interval.power_ftp_min / 100));
          }
          if (interval.power_ftp_max !== undefined) {
            newInterval.power_watt_max = Math.round(athleteFtp * (interval.power_ftp_max / 100));
          }
        } else if (!isCycling && athleteVma) {
          if (interval.pace_vma_min !== undefined && interval.pace_vma_max !== undefined) {
            newInterval.pace_min = convertVmaPercentageToPace(athleteVma, interval.pace_vma_min);
            newInterval.pace_max = convertVmaPercentageToPace(athleteVma, interval.pace_vma_max);
          }
        }
        return newInterval;
      });
      
      // Calculer la durée pour ce block
      if (processedIntervals) {
        processedIntervals.forEach((interval: any) => {
          if (interval.duration) {
            totalDuration += interval.duration * repetitions;
          }
        });
      }
      
      return { ...block, intervals: processedIntervals };
    });

    setEditFormData({
      ...editFormData,
      name: catalogWorkout.name,
      sport: catalogWorkout.sport || 'running',
      workout_type: catalogWorkout.workout_type,
      duration_minutes: Math.round(totalDuration),
      difficulty_level: catalogWorkout.perceived_difficulty || 5,
      description: catalogWorkout.description || '',
      scheme: processedScheme
    });
    setCatalogAthleteId(editFormData.athlete_id);
    setShowCatalogModal(false);
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (catalogAthleteId !== null && catalogAthleteId !== editFormData.athlete_id) {
      alert("Sélectionnez à nouveau la séance du catalogue pour utiliser les statistiques du nouvel athlète.");
      return;
    }
    setIsValidating(true);
    try {
      const response = await fetchWithAuth(`/api/workouts/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...editFormData,
          date: format(new Date(editFormData.date), "yyyy-MM-dd'T'HH:mm:ss")
        }),
      });
      if (response.ok) {
        const updated = await response.json();
        setWorkout(updated);
        setIsEditing(false);
      }
    } catch (error) {
      console.error('Update failed:', error);
    } finally {
      setIsValidating(false);
    }
  };

  const handleOpenCatalog = async () => {
    if (catalogWorkouts.length === 0) {
      await fetchCatalog();
    }
    setShowCatalogModal(true);
  };

  const handleDelete = async () => {
    if (!window.confirm('Êtes-vous sûr de vouloir supprimer cette séance ?')) return;
    try {
      const response = await fetchWithAuth(`/api/workouts/${id}`, {
        method: 'DELETE',
      });
      if (response.ok) {
        router.push('/');
      }
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const handleValidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsValidating(true);
    try {
      const response = await fetchWithAuth(`/api/workouts/${id}/validate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          perceived_difficulty: perceivedDifficulty,
          athlete_comment: comment
        }),
      });
      if (response.ok) {
        const updated = await response.json();
        setWorkout(updated);
      }
    } catch (error) {
      console.error('Validation failed:', error);
    } finally {
      setIsValidating(false);
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center">Chargement...</div>;
  if (!workout) return <div className="min-h-screen flex items-center justify-center">Séance non trouvée</div>;

  const needsCalendarDuration = !Number.isInteger(workout.duration_minutes) || workout.duration_minutes <= 0;
  const calendarWorkout = {
    name: workout.name,
    date: workout.date,
    duration_minutes: needsCalendarDuration ? Number(calendarDuration) : workout.duration_minutes,
    description: workout.description,
  };
  let calendarDate: Date | null = null;
  let calendarError: string | null = null;
  let googleCalendarUrl: string | null = null;
  try {
    calendarDate = createCalendarEvent({ ...calendarWorkout, duration_minutes: 1 }).start;
    createCalendarEvent(calendarWorkout);
    googleCalendarUrl = createGoogleCalendarUrl(calendarWorkout);
  } catch (error) {
    calendarError = error instanceof Error ? error.message : 'Impossible de préparer le calendrier';
  }

  const handleIcsDownload = () => {
    try {
      const blob = new Blob([createIcsCalendar(calendarWorkout)], { type: 'text/calendar;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${(workout.name || 'seance').replace(/[^A-Za-z0-9_.-]+/g, '_')}.ics`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Impossible de créer le fichier calendrier');
    }
  };

  return (
    <main className="min-h-screen bg-brand-surface pb-20 font-sans">
      {/* Header compact sur mobile */}
      <div className="bg-brand-dark border-b border-brand-primary/20 sticky top-0 z-50 shadow-lg shadow-brand-dark/10">
        <div className="max-w-5xl mx-auto px-4 md:px-6 h-16 md:h-20 flex items-center justify-between gap-2">
          <Link href="/" className="flex items-center gap-2 text-brand-secondary hover:text-white transition-all group">
            <div className="p-2 bg-brand-primary/20 rounded-xl group-hover:bg-brand-primary group-hover:text-white transition-all">
              <ChevronLeft className="w-5 h-5" />
            </div>
            <span className="hidden md:inline font-black uppercase text-[10px] tracking-[0.2em]">Retour au calendrier</span>
          </Link>
          <div className="flex items-center gap-2 md:gap-4">
            {isCoach && !isEditing && (
              <div className="flex gap-2">
                <button 
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-2 bg-brand-primary text-white px-3 md:px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-secondary transition-all shadow-lg"
                >
                  <Edit2 className="w-4 h-4" /> <span className="hidden sm:inline">Modifier</span>
                </button>
                <button 
                  onClick={handleDelete}
                  className="flex items-center gap-2 bg-red-500 text-white px-3 md:px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-red-600 transition-all shadow-lg shadow-red-100"
                >
                  <Trash2 className="w-4 h-4" /> <span className="hidden sm:inline">Supprimer</span>
                </button>
              </div>
            )}
            {workout.is_validated && (
              <span className="flex items-center gap-1.5 text-white bg-green-500 px-3 md:px-4 py-1.5 rounded-full text-[9px] md:text-[10px] font-black uppercase tracking-widest shadow-lg shadow-green-100">
                <CheckCircle2 className="w-3.5 h-3.5 md:w-4 md:h-4" /> Validée
              </span>
            )}
            <span className="hidden sm:inline text-brand-secondary font-bold uppercase text-[10px] tracking-widest">{calendarDate ? format(calendarDate, 'd MMMM yyyy', { locale: fr }) : 'Date invalide'}</span>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 md:px-6 mt-6 md:mt-12 space-y-6 md:space-y-12">
        {isEditing ? (
          <section className="bg-white rounded-[2rem] md:rounded-[3rem] p-6 md:p-16 shadow-[0_40px_80px_-20px_rgba(0,0,0,0.06)] border border-brand-light/50">
            <h2 className="text-2xl md:text-4xl font-black text-brand-dark uppercase tracking-tighter mb-6 md:mb-12">Modifier la séance</h2>
            <form onSubmit={handleUpdate} className="space-y-6 md:space-y-8">
              
              {/* Coach-only athlete selector */}
              {isCoach && (
                <div className="space-y-2 pb-6 border-b border-brand-surface">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1 flex items-center gap-2">
                    <Users className="w-3 h-3" />
                    Attribuer à l'athlète
                  </label>
                  <select
                    className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer text-brand-dark"
                    value={editFormData.athlete_id || ''}
                    onChange={e => {
                      setAthleteVma(null);
                      setAthleteFtp(null);
                      setEditFormData({...editFormData, athlete_id: e.target.value ? parseInt(e.target.value) : null});
                    }}
                    required
                  >
                    <option value="">Choisir un athlète...</option>
                    {user && (
                      <option value={user.id}>Moi-même ({user.email})</option>
                    )}
                    {athletes.map(a => (
                      <option key={a.id} value={a.id}>{a.email}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="flex justify-end mb-4">
                <button
                  type="button"
                  onClick={handleOpenCatalog}
                  disabled={!athleteVma && !athleteFtp}
                  title={(!athleteVma && !athleteFtp) ? "Les statistiques de l'athlète (VMA/FTP) ne sont pas disponibles." : undefined}
                  className="flex items-center gap-2 bg-white text-brand-dark border border-brand-light px-4 py-2 rounded-xl font-black uppercase text-[10px] tracking-widest hover:bg-brand-primary hover:text-white transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <BookOpen className="w-4 h-4" />
                  Choisir du catalogue
                </button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 md:gap-8">
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Discipline</label>
                  <select
                    className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer text-brand-dark"
                    value={editFormData.sport}
                    onChange={e => setEditFormData({...editFormData, sport: e.target.value as 'running' | 'cycling'})}
                  >
                    <option value="running">Course à pied</option>
                    <option value="cycling">Cyclisme</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Nom de la séance</label>
                  <input
                    type="text"
                    className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark"
                    value={editFormData.name}
                    onChange={e => setEditFormData({...editFormData, name: e.target.value})}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Type de séance</label>
                  <select
                    className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer text-brand-dark"
                    value={editFormData.workout_type}
                    onChange={e => setEditFormData({...editFormData, workout_type: e.target.value})}
                  >
                    {['Libre', 'Endurance', 'Fractionné', 'Sortie Longue', 'Trail', 'Tempo', 'VO2 Max', 'Seuil'].map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Date & Heure</label>
                  <input
                    type="datetime-local"
                    className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark"
                    value={editFormData.date}
                    onChange={e => setEditFormData({...editFormData, date: e.target.value})}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Durée (min)</label>
                    <input
                      type="number"
                      className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark"
                      value={editFormData.duration_minutes}
                      onChange={e => setEditFormData({...editFormData, duration_minutes: parseInt(e.target.value)})}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Difficulté (1-10)</label>
                    <input
                      type="number"
                      min="1"
                      max="10"
                      className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none transition-all font-bold text-brand-dark"
                      value={editFormData.difficulty_level}
                      onChange={e => setEditFormData({...editFormData, difficulty_level: parseInt(e.target.value)})}
                    />
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Description</label>
                <textarea
                  className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none font-bold text-sm min-h-[150px] text-brand-dark"
                  value={editFormData.description}
                  onChange={e => setEditFormData({...editFormData, description: e.target.value})}
                />
              </div>

              <div className="space-y-4">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary ml-1">Structure (JSON)</label>
                <textarea
                  className="w-full px-6 py-4 rounded-2xl bg-brand-surface border-2 border-transparent focus:border-brand-primary focus:bg-white outline-none font-mono text-xs min-h-[200px] text-brand-dark"
                  value={JSON.stringify(editFormData.scheme, null, 2)}
                  onChange={e => {
                    try {
                      setEditFormData({...editFormData, scheme: JSON.parse(e.target.value)});
                    } catch (err) {
                      // Ignorer si JSON invalide en cours de frappe
                    }
                  }}
                />
              </div>
              
              <div className="flex gap-4 pt-4">
                <button
                  type="submit"
                  disabled={isValidating}
                  className="flex-1 py-4 md:py-6 rounded-2xl md:rounded-[2rem] bg-brand-primary text-white font-black uppercase text-xs md:text-sm tracking-[0.2em] md:tracking-[0.3em] hover:bg-brand-secondary transition-all shadow-xl shadow-brand-primary/10 disabled:opacity-50"
                >
                  {isValidating ? 'Enregistrement...' : 'Sauvegarder'}
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="px-6 md:px-10 py-4 md:py-6 rounded-2xl md:rounded-[2rem] bg-brand-surface text-brand-dark font-black uppercase text-xs md:text-sm tracking-[0.2em] md:tracking-[0.3em] hover:bg-brand-light transition-all border border-brand-light"
                >
                  Annuler
                </button>
              </div>
            </form>
          </section>
        ) : (
          <>
            {/* Main Info */}
            <section className="bg-white rounded-[2rem] md:rounded-[3rem] p-6 md:p-16 shadow-[0_40px_80px_-20px_rgba(0,0,0,0.06)] border border-brand-light/50 relative overflow-hidden">
              <div className="absolute top-0 left-0 w-3 h-full bg-brand-primary" />
              
              <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 md:gap-10 mb-8 md:mb-16">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-4 md:mb-8">
                    <span className="px-3 md:px-4 py-1.5 rounded-full text-[9px] md:text-[10px] font-black bg-brand-accent text-white uppercase tracking-widest shadow-sm shadow-brand-accent/20">
                      {workout.workout_type}
                    </span>
                    <span className="w-8 h-[2px] bg-brand-surface" />
                  </div>
                  <h1 className="text-3xl sm:text-5xl md:text-6xl lg:text-7xl font-black text-brand-dark leading-[1.05] md:leading-[0.9] uppercase tracking-tighter mb-2 md:mb-6">{workout.name}</h1>
                  <div className="flex items-center gap-4 md:gap-6 text-brand-secondary font-black uppercase text-[9px] md:text-[10px] tracking-[0.2em]">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      {calendarDate ? format(calendarDate, 'EEEE d MMMM', { locale: fr }) : 'Date de séance invalide'}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2 mt-4 md:mt-6">
                    <button
                      onClick={handleGarminExport}
                      disabled={isCheckingGarmin}
                      className="flex items-center gap-2 bg-brand-primary text-white px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-secondary transition-all shadow-lg active:scale-[0.98] disabled:opacity-50"
                    >
                      <Watch className="w-4 h-4" />
                      Telecharger fichier FIT
                    </button>
                    <button
                      onClick={handlePushGarmin}
                      disabled={isCheckingGarmin}
                      className="flex items-center gap-2 bg-brand-dark text-white px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-primary transition-all shadow-lg active:scale-[0.98] disabled:opacity-50 border border-brand-primary/20"
                    >
                      {isCheckingGarmin ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Watch className="w-4 h-4" />
                      )}
                      {garminConnected ? 'Envoyer vers Garmin' : 'Connecter à Garmin'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowCalendar(!showCalendar)}
                      aria-expanded={showCalendar}
                      aria-controls="calendar-export"
                      className="flex items-center gap-2 bg-brand-surface text-brand-dark px-5 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest hover:bg-brand-light transition-all border border-brand-light"
                    >
                      <Calendar className="w-4 h-4" /> Ajouter à mon calendrier
                    </button>
                  </div>
                  {showCalendar && (
                    <div id="calendar-export" className="mt-4 p-4 bg-brand-surface border border-brand-light rounded-xl space-y-4 text-sm text-brand-dark">
                      <p>Heure locale proposée : {calendarDate ? format(calendarDate, "EEEE d MMMM yyyy 'à' HH:mm", { locale: fr }) : 'date de séance invalide'}.</p>
                      {needsCalendarDuration && (
                        <div className="space-y-2">
                          <label htmlFor="calendar-duration" className="block font-bold">Durée pour le calendrier (minutes)</label>
                          <input
                            id="calendar-duration"
                            type="number"
                            min="1"
                            step="1"
                            inputMode="numeric"
                            value={calendarDuration}
                            onChange={e => setCalendarDuration(e.target.value)}
                            aria-describedby="calendar-error"
                            className="w-full sm:w-40 px-4 py-3 rounded-xl border border-brand-light bg-white text-brand-dark"
                          />
                        </div>
                      )}
                      {calendarError && <p id="calendar-error" role="alert" className="text-red-700">{calendarError === 'Durée de séance invalide' ? 'Indiquez une durée entière positive en minutes.' : calendarError}</p>}
                      <p>Google Agenda s’ouvre dans le navigateur : vous devez y confirmer l’ajout. Pour Calendrier sur iPhone ou une autre application, ouvrez le fichier ICS téléchargé et confirmez l’ajout ; son ouverture dépend de votre navigateur.</p>
                      <p>Aucune synchronisation automatique : les modifications ne sont pas répercutées et chaque ajout peut créer un doublon.</p>
                      <div className="flex flex-wrap gap-2">
                        {googleCalendarUrl && (
                          <a href={googleCalendarUrl} target="_blank" rel="noopener noreferrer" className="px-4 py-3 rounded-xl bg-brand-primary text-white font-bold">Google Agenda (nouvel onglet)</a>
                        )}
                        <button type="button" onClick={handleIcsDownload} disabled={!googleCalendarUrl} className="px-4 py-3 rounded-xl bg-brand-dark text-white font-bold disabled:opacity-50">Télécharger le fichier ICS</button>
                      </div>
                    </div>
                  )}
                  {pushError && (
                    <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-red-600">{pushError}</span>
                        {pushError.includes('reconnect') && (
                          <button 
                            onClick={() => setShowGarminAuthModal(true)}
                            className="flex-shrink-0 flex items-center gap-1.5 bg-red-600 text-white px-3 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-widest hover:bg-red-700 transition-all shadow-md"
                          >
                            <RefreshCw className="w-3 h-3" />
                            Reconnecter
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                  {pushSuccess && (
                    <div className="mt-4 p-3 bg-green-50 border border-green-200 rounded-xl">
                      <span className="text-sm font-medium text-green-600">Séance envoyée avec succès vers Garmin !</span>
                    </div>
                  )}
                  {garminConnected && garminEmail && (
                    <div className="mt-4 flex items-center gap-2 text-sm text-brand-secondary font-medium">
                      <Link2 className="w-4 h-4 text-green-500" />
                      Connecté à: <span className="font-black text-brand-dark">{garminEmail}</span>
                    </div>
                  )}
                </div>
                
                {/* Statistiques : bandeau compact sur mobile, cartes larges sur desktop */}
                <div className="grid grid-cols-3 gap-2 md:gap-4 lg:flex lg:flex-wrap">
                  <div className="bg-brand-dark text-white px-2 py-3 md:px-10 md:py-8 rounded-xl md:rounded-[2.5rem] flex flex-col items-center justify-center shadow-lg md:shadow-2xl md:shadow-brand-dark/20 border border-brand-primary/20">
                    <Clock className="w-4 h-4 md:w-8 md:h-8 mb-1 md:mb-4 text-brand-accent" />
                    <span className="text-lg md:text-4xl font-black leading-none">{workout.duration_minutes}</span>
                    <span className="text-[8px] md:text-[10px] uppercase font-black tracking-widest mt-1 md:mt-2 opacity-50">Minutes</span>
                  </div>
                  <div className="bg-white text-brand-dark px-2 py-3 md:px-10 md:py-8 rounded-xl md:rounded-[2.5rem] flex flex-col items-center justify-center border border-brand-light shadow-sm">
                    <Activity className="w-4 h-4 md:w-8 md:h-8 mb-1 md:mb-4 text-brand-primary" />
                    <span className="text-lg md:text-4xl font-black leading-none">{workout.difficulty_level}</span>
                    <span className="text-[8px] md:text-[10px] uppercase font-black tracking-widest mt-1 md:mt-2 opacity-50">Intensité</span>
                  </div>
                  <div className="bg-brand-surface text-brand-dark px-2 py-3 md:px-10 md:py-8 rounded-xl md:rounded-[2.5rem] flex flex-col items-center justify-center border border-brand-light">
                    <Dumbbell className="w-4 h-4 md:w-8 md:h-8 mb-1 md:mb-4 text-brand-secondary" />
                    <span className="text-lg md:text-4xl font-black leading-none">{workout.estimated_load?.toFixed(0)}</span>
                    <span className="text-[8px] md:text-[10px] uppercase font-black tracking-widest mt-1 md:mt-2 opacity-50">Charge</span>
                  </div>
                </div>
              </div>

              <div className="space-y-6 md:space-y-10 border-t border-brand-surface pt-8 md:pt-16">
                <div className="max-w-3xl">
                  <h4 className="font-black text-[9px] md:text-[10px] text-brand-secondary uppercase tracking-[0.3em] mb-4 md:mb-8 flex items-center gap-3">
                    <div className="w-2 h-2 bg-brand-primary rounded-full" />
                    Objectifs & Description
                  </h4>
                  <p className="text-brand-dark text-base md:text-3xl leading-relaxed md:leading-snug font-medium italic tracking-tight">
                    "{workout.description}"
                  </p>
                </div>

                {workout.scheme && workout.scheme.length > 0 && (
                  <div className="pt-4 md:pt-8">
                    <h4 className="font-black text-[9px] md:text-[10px] text-brand-secondary uppercase tracking-[0.3em] mb-4 md:mb-8 flex items-center gap-3">
                      <div className="w-2 h-2 bg-brand-accent rounded-full" />
                      Structure de l'exercice
                    </h4>
                    <div className="space-y-3 md:space-y-6">
                      {workout.scheme.map((block: WorkoutBlock, bIdx: number) => (
                        <div key={bIdx} className="bg-brand-surface p-3 md:p-8 rounded-2xl md:rounded-[2.5rem] border border-brand-light relative group overflow-hidden">
                          <div className="absolute top-0 left-0 w-2 h-full bg-brand-accent opacity-20 group-hover:opacity-100 transition-all" />
                          
                          {block.repetitions > 1 && (
                            <div className="flex items-center gap-2 mb-3 md:mb-6 ml-2">
                              <div className="bg-brand-dark text-white p-1.5 md:p-2 rounded-lg md:rounded-xl">
                                <RotateCcw className="w-3.5 h-3.5 md:w-4 md:h-4" />
                              </div>
                              <span className="font-black text-[9px] md:text-[10px] uppercase tracking-[0.2em] text-brand-dark">Répéter {block.repetitions} fois</span>
                            </div>
                          )}

                          <div className="space-y-2 md:space-y-4">
                            {block.intervals.map((interval, iIdx) => (
                              <div key={iIdx} className="bg-white p-3 md:p-8 rounded-xl md:rounded-[2rem] border border-brand-light flex flex-col md:flex-row md:items-center justify-between group/item hover:border-brand-primary transition-all shadow-sm">
                                <div className="flex items-center gap-3 md:gap-8 mb-2 md:mb-0">
                                  <div className="w-8 h-8 md:w-12 md:h-12 bg-brand-surface rounded-lg md:rounded-2xl flex items-center justify-center font-black text-sm md:text-base text-brand-dark border border-brand-light group-hover/item:bg-brand-primary group-hover/item:text-white transition-all">
                                    {iIdx + 1}
                                  </div>
                                  <div>
                                    <div className="font-black uppercase tracking-tighter text-sm md:text-xl mb-0.5 md:mb-1 text-brand-dark">{interval.type}</div>
                                    <div className="text-brand-secondary font-bold text-[9px] md:text-[10px] uppercase tracking-widest flex items-center gap-2">
                                      <span className="w-2 h-[2px] bg-brand-accent" />
                                      {workout.sport === 'cycling' ? (
                                        <>Puissance: {interval.power_watt_min}W {interval.power_watt_max && interval.power_watt_max !== interval.power_watt_min ? `- ${interval.power_watt_max}W` : ''}</>
                                      ) : (
                                        <>Allure: {interval.pace_min} {interval.pace_max && interval.pace_max !== interval.pace_min ? `- ${interval.pace_max}` : ''}</>
                                      )}
                                    </div>
                                  </div>
                                </div>
                                <div className="flex md:block items-end justify-between border-t md:border-t-0 border-brand-surface pt-2 md:pt-0">
                                  <span className="text-[9px] font-black uppercase tracking-widest text-brand-secondary md:hidden">Volume</span>
                                  <div className="text-xl md:text-4xl font-black tracking-tighter text-brand-dark">
                                    {interval.duration || interval.distance}
                                    <span className="text-[10px] md:text-sm ml-1 md:ml-2 opacity-30 font-bold uppercase">{interval.duration !== undefined ? 'min' : 'm'}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </section>

            {/* Validation Section */}
            <section className="bg-brand-dark text-white rounded-[2rem] md:rounded-[3rem] p-6 md:p-16 shadow-[0_40px_80px_-20px_rgba(30,58,138,0.3)] relative overflow-hidden border border-brand-primary/20">
              <div className="absolute top-0 right-0 w-64 h-64 bg-brand-accent rounded-bl-[10rem] opacity-5 -mr-16 -mt-16" />
              
              {!workout.is_validated ? (
                <>
                  <div className="flex items-center gap-3 md:gap-4 mb-6 md:mb-12">
                    <div className="w-10 h-10 md:w-12 md:h-12 bg-brand-accent rounded-xl md:rounded-2xl flex items-center justify-center shadow-lg shadow-brand-accent/20">
                      <Activity className="w-5 h-5 md:w-6 md:h-6 text-white" />
                    </div>
                    <h2 className="text-2xl md:text-4xl font-black uppercase tracking-tighter">Valider la séance</h2>
                  </div>
                  
                  <form onSubmit={handleValidate} className="space-y-6 md:space-y-12 max-w-4xl">
                    <div className="space-y-4 md:space-y-6">
                      <div className="flex justify-between items-end">
                        <label className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-40">Difficulté ressentie</label>
                        <div className="text-4xl md:text-6xl font-black text-brand-accent leading-none">{perceivedDifficulty}<span className="text-base md:text-xl ml-2 opacity-30">/10</span></div>
                      </div>
                      <input 
                        type="range" 
                        min="1" 
                        max="10" 
                        step="1"
                        value={perceivedDifficulty}
                        onChange={(e) => setPerceivedDifficulty(parseInt(e.target.value))}
                        className="w-full h-3 md:h-4 bg-white/10 rounded-full appearance-none cursor-pointer accent-brand-accent"
                      />
                      <div className="flex justify-between text-[8px] md:text-[9px] font-black uppercase tracking-[0.3em] opacity-30">
                        <span>Facile</span>
                        <span>Modéré</span>
                        <span>Épuisant</span>
                      </div>
                    </div>

                    <div className="space-y-4 md:space-y-6">
                      <label className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-40 flex items-center gap-3">
                        <AlignLeft className="w-4 h-4 text-brand-accent" />
                        Compte-rendu de l'athlète
                      </label>
                      <textarea 
                        rows={6}
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Quelles sont vos sensations ? Des points d'attention particuliers ?"
                        className="w-full bg-white/5 border border-white/10 rounded-2xl md:rounded-[2rem] p-4 md:p-8 text-white text-sm md:text-lg placeholder:text-white/10 focus:outline-none focus:border-brand-accent focus:bg-white/10 transition-all min-h-[120px] md:min-h-[180px] font-medium"
                      />
                    </div>

                    <button 
                      type="submit"
                      disabled={isValidating}
                      className="w-full bg-brand-primary hover:bg-brand-secondary text-white font-black uppercase tracking-[0.2em] text-xs md:text-sm py-5 md:py-8 rounded-2xl md:rounded-[2rem] transition-all shadow-[0_20px_40px_-10px_rgba(37,99,235,0.3)] active:scale-[0.98] flex items-center justify-center gap-3 md:gap-4 disabled:opacity-50 group border border-brand-primary/20"
                    >
                      {isValidating ? 'TRANSMISSION...' : (
                        <>
                          <Send className="w-5 h-5 transition-transform group-hover:translate-x-1 group-hover:-translate-y-1" />
                          ENREGISTRER LA SÉANCE
                        </>
                      )}
                    </button>
                  </form>
                </>
              ) : (
                <div className="space-y-6 md:space-y-12">
                  <div className="flex items-center gap-3 md:gap-4 mb-6 md:mb-8">
                    <div className="w-10 h-10 md:w-12 md:h-12 bg-green-500 rounded-xl md:rounded-2xl flex items-center justify-center shadow-lg shadow-green-500/20">
                      <CheckCircle2 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                    </div>
                    <h2 className="text-2xl md:text-4xl font-black uppercase tracking-tighter">Séance Enregistrée</h2>
                  </div>
                  
                  <div className="grid md:grid-cols-3 gap-6 md:gap-12 relative z-10">
                    <div className="space-y-2 md:space-y-4">
                      <div className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-40 text-brand-accent">Ressenti</div>
                      <div className="text-5xl md:text-7xl font-black">{workout.perceived_difficulty}<span className="text-lg md:text-2xl ml-2 opacity-20">/10</span></div>
                    </div>
                    <div className="md:col-span-2 space-y-2 md:space-y-4">
                      <div className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-40 text-brand-accent">Commentaires</div>
                      <div className="text-base md:text-2xl font-medium italic leading-relaxed border-l-4 border-brand-accent pl-4 md:pl-8 py-2">
                        "{workout.athlete_comment || "Aucun commentaire laissé."}"
                      </div>
                    </div>
                  </div>
                  
                  <div className="pt-6 md:pt-12 border-t border-white/10 mt-6 md:mt-12 flex flex-col md:flex-row items-center justify-between gap-4">
                    <div className="flex items-center gap-3 md:gap-4">
                      <div className="w-8 h-8 md:w-10 md:h-10 bg-green-500/20 rounded-full flex items-center justify-center">
                        <CheckCircle2 className="w-4 h-4 md:w-5 md:h-5 text-green-500" />
                      </div>
                      <div className="text-xs md:text-sm font-bold opacity-60 text-brand-secondary">Transmission effectuée au coach</div>
                    </div>
                    <Link href="/" className="text-[10px] font-black uppercase tracking-[0.2em] text-brand-secondary hover:text-brand-accent transition-colors">
                      Retour à la vue d'ensemble →
                    </Link>
                  </div>
                </div>
              )}
            </section>
          </>
        )}
      </div>
      {/* Catalog Modal */}
      {showCatalogModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          onClick={() => setShowCatalogModal(false)}
        >
          <div
            className="bg-white rounded-[2.5rem] p-8 max-w-2xl w-full shadow-2xl border border-brand-light max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="bg-brand-accent p-2 rounded-xl text-white shadow-lg shadow-brand-accent/20">
                  <BookOpen className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-xl font-black text-brand-dark uppercase tracking-tight">Sélectionner une séance du catalogue</h3>
                  {athleteVma && (
                    <p className="text-sm text-brand-secondary font-medium mt-1">VMA de l'athlète : <span className="font-black text-brand-dark">{athleteVma} km/h</span></p>
                  )}
                </div>
              </div>
              <button
                onClick={() => setShowCatalogModal(false)}
                className="p-2 text-brand-secondary hover:text-brand-dark hover:bg-brand-surface rounded-xl transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            {loadingCatalog ? (
              <div className="text-center py-12 font-black uppercase text-brand-secondary tracking-widest animate-pulse">Chargement du catalogue...</div>
            ) : catalogWorkouts.length === 0 ? (
              <div className="text-center py-12 font-black uppercase text-brand-secondary tracking-widest">Aucune séance dans le catalogue</div>
            ) : (
              <div className="grid grid-cols-1 gap-4">
                {catalogWorkouts.map((catalogWorkout) => (
                  <button
                    key={catalogWorkout.id}
                    onClick={() => handleSelectFromCatalog(catalogWorkout)}
                    className="w-full bg-brand-surface hover:bg-brand-primary hover:text-white border border-brand-light rounded-2xl p-6 text-left transition-all group"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="text-lg font-black uppercase tracking-tight group-hover:text-brand-accent">{catalogWorkout.name}</h4>
                        <div className="flex items-center gap-4 mt-2 text-sm font-medium text-brand-secondary group-hover:text-white/70">
                          <span className="text-[10px] font-black uppercase tracking-widest">{catalogWorkout.workout_type}</span>
                          <span className="text-[10px] font-black uppercase tracking-widest">Difficulté : {catalogWorkout.perceived_difficulty}/10</span>
                        </div>
                      </div>
                      <div className="text-brand-primary group-hover:text-white">
                        <ChevronLeft className="w-5 h-5 transform -rotate-180" />
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
            
            <div className="mt-8 flex justify-end">
              <button
                onClick={() => setShowCatalogModal(false)}
                className="px-6 py-3 bg-brand-surface text-brand-dark rounded-2xl font-black uppercase text-[10px] tracking-widest hover:bg-brand-light transition-all border border-brand-light"
              >
                Annuler
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Garmin Auth Modal */}
      <GarminAuthModal
        isOpen={showGarminAuthModal}
        onClose={() => setShowGarminAuthModal(false)}
        onSuccess={handleGarminAuthSuccess}
        currentEmail={garminEmail || ''}
        isConnected={garminConnected}
      />

      {showGarminHelp && (
         <div
           className="fixed inset-0 bg-black/40 backdrop-blur-md z-50 flex items-center justify-center p-4"
           onClick={() => setShowGarminHelp(false)}
         >
           <div
             className="bg-white rounded-2xl md:rounded-[2rem] max-w-md w-full p-6 md:p-8 space-y-5 border border-brand-light shadow-2xl"
             onClick={e => e.stopPropagation()}
           >
             <div className="flex items-center gap-3">
               <div className="bg-brand-dark p-2.5 rounded-xl shadow-lg shadow-brand-dark/10">
                 <Watch className="w-5 h-5 text-white" />
               </div>
               <h3 className="text-lg font-black text-brand-dark uppercase tracking-tight">Fichier Garmin téléchargé</h3>
             </div>
             <p className="text-sm text-brand-secondary font-medium leading-relaxed">
               Votre séance <strong className="text-brand-dark">{workout.name}</strong> a été exportée au format{' '}
               <strong className="text-brand-dark">.fit</strong>. Pour l'importer dans Garmin Connect :
             </p>
             <ol className="space-y-2 text-sm text-brand-secondary font-medium list-decimal list-inside">
               <li>Ouvrez <strong className="text-brand-dark">connect.garmin.com</strong> depuis un navigateur (l'import n'est pas possible depuis l'app mobile)</li>
               <li>Allez dans <strong className="text-brand-dark">Training / Entraînements</strong> → <strong className="text-brand-dark">Workouts / Entraînements</strong></li>
               <li>Cliquez sur <strong className="text-brand-dark">Importer</strong> (icône + ou roue dentée selon la version) et sélectionnez le fichier <strong className="text-brand-dark">.fit</strong> téléchargé</li>
               <li>La séance apparaît dans vos entraînements et se synchronise automatiquement vers votre montre Garmin</li>
             </ol>
             <button
               onClick={() => setShowGarminHelp(false)}
               className="w-full bg-brand-primary text-white font-black uppercase text-xs tracking-widest py-4 rounded-2xl hover:bg-brand-secondary transition-all shadow-lg shadow-brand-primary/20"
             >
               Compris
             </button>
           </div>
         </div>
       )}
    </main>
  );
}
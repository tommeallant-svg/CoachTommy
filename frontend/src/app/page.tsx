'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { 
  format, 
  startOfMonth, 
  endOfMonth, 
  startOfWeek, 
  endOfWeek, 
  eachDayOfInterval, 
  isSameMonth, 
  isSameDay, 
  addMonths, 
  subMonths, 
  addWeeks, 
  subWeeks,
  parseISO,
  setDay,
  isAfter,
  isBefore
} from 'date-fns';
import { fr } from 'date-fns/locale';
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon, 
  LayoutList,
  ExternalLink,
  X,
  CheckCircle2, 
  Clock, 
  ArrowRightLeft, 
  Activity, 
  Zap,
  AlignLeft, 
  Plus,
  LogOut,
  Users,
  Dumbbell,
  Watch,
  Droplets
} from 'lucide-react';
import Link from 'next/link';
import { Workout } from '@/types/workout';
import { useRouter, useSearchParams } from 'next/navigation';
import { 
  fetchWithAuth, 
  getAuthToken, 
  clearAuthToken, 
  getAuthUser 
} from '@/lib/api';
import GarminAuthModal from '@/components/GarminAuthModal';
import MenstrualCycleModal from '@/components/MenstrualCycleModal';
import AthleteStatsModal from '@/components/AthleteStatsModal';
import { User } from '@/types/user';
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';

// Couleurs par type de séance (style moderne avec dégradés et ombres)
const TYPE_COLORS: Record<string, { bar: string; chip: string; text: string; dot: string }> = {
  'Endurance':     { bar: 'border-l-emerald-500',  chip: 'bg-emerald-50',  text: 'text-emerald-900', dot: 'bg-emerald-500' },
  'Tempo':         { bar: 'border-l-brand-primary',chip: 'bg-brand-surface',text: 'text-brand-dark',  dot: 'bg-brand-primary' },
  'Seuil':         { bar: 'border-l-amber-500',   chip: 'bg-amber-50',    text: 'text-amber-900',   dot: 'bg-amber-500' },
  'VO2 Max':       { bar: 'border-l-rose-500',    chip: 'bg-rose-50',     text: 'text-rose-900',    dot: 'bg-rose-500' },
  'Fractionné':    { bar: 'border-l-indigo-500',  chip: 'bg-indigo-50',   text: 'text-indigo-900',  dot: 'bg-indigo-500' },
  'Sortie Longue': { bar: 'border-l-cyan-500',    chip: 'bg-cyan-50',     text: 'text-cyan-900',    dot: 'bg-cyan-500' },
  'Trail':         { bar: 'border-l-orange-700',  chip: 'bg-orange-50',   text: 'text-orange-900',  dot: 'bg-orange-700' },
  'Libre':         { bar: 'border-l-slate-400',   chip: 'bg-slate-50',    text: 'text-slate-900',   dot: 'bg-slate-400' },
};
const DEFAULT_COLOR = { bar: 'border-l-brand-dark', chip: 'bg-brand-surface', text: 'text-brand-dark', dot: 'bg-brand-dark' };

function DraggableWorkout({ workout, onClick }: { workout: Workout, onClick: () => void }) {
  const {attributes, listeners, setNodeRef, transform} = useDraggable({
    id: `workout-${workout.id}`,
    data: { workout }
  });
  
  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: 100,
  } : undefined;

  const colors = TYPE_COLORS[workout.workout_type] || DEFAULT_COLOR;

  return (
    <div 
      ref={setNodeRef}
      style={style}
      {...listeners}
      {...attributes}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`w-full flex items-center gap-1 px-1.5 py-1 rounded-md border-l-[3px] ${colors.bar} ${colors.chip} cursor-grab active:cursor-grabbing transition-all hover:shadow-md active:scale-[0.98] ${
        workout.is_validated ? 'opacity-60' : ''
      }`}
    >
      <span className="hidden md:inline shrink-0 font-black text-brand-secondary/50 tabular-nums">
        {format(parseISO(workout.date), 'HH:mm')}
      </span>
      <div className={`w-1.5 h-1.5 rounded-full ${colors.dot} shrink-0`} />
      <span className={`truncate font-bold leading-tight text-[10px] md:text-xs ${colors.text}`}>
        {workout.name}
      </span>
      {workout.is_validated && (
        <CheckCircle2 className="w-2.5 h-2.5 md:w-3 md:h-3 text-green-600 shrink-0" />
      )}
    </div>
  );
}

function DayDroppable({ day, children, isToday, isNotCurrentMonth }: any) {
  const {setNodeRef, isOver} = useDroppable({
    id: day.toISOString(),
  });

  return (
    <div 
      ref={setNodeRef}
      className={`min-h-[72px] md:min-h-[160px] p-1 md:p-3 border-r border-t border-brand-light/30 transition-all ${
        isNotCurrentMonth ? 'bg-slate-50/50 text-slate-300' : 'bg-white'
      } ${isToday ? 'bg-brand-surface' : ''} ${isOver ? 'bg-brand-light/30 ring-2 ring-brand-primary/20 ring-inset shadow-inner' : ''}`}
    >
      <div className="flex justify-between items-start mb-1 md:mb-2">
        <span className={`text-[10px] md:text-sm font-black tracking-tighter ${
          isToday 
            ? 'bg-brand-primary text-white w-5 h-5 md:w-8 md:h-8 flex items-center justify-center rounded-md md:rounded-lg shadow-lg shadow-brand-primary/20' 
            : isNotCurrentMonth ? 'text-slate-300' : 'text-slate-400'
        }`}>
          {format(day, 'd')}
        </span>
      </div>
      <div className="space-y-0.5 md:space-y-2">
        {children}
      </div>
    </div>
  );
}

function CalendarPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const athleteId = searchParams.get('athleteId');
  
  const [user, setUser] = useState<User | null>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<'month' | 'week'>('month');
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [selectedWorkout, setSelectedWorkout] = useState<Workout | null>(null);
  const [isSideMenuOpen, setIsSideMenuOpen] = useState(false);
  const [currentPlan, setCurrentPlan] = useState<any>(null);
  const [showGarminAuthModal, setShowGarminAuthModal] = useState(false);
  const [showMenstrualModal, setShowMenstrualModal] = useState(false);
  const [showStatsModal, setShowStatsModal] = useState(false);
  const [garminStatus, setGarminStatus] = useState({ is_connected: false, garmin_email: '' });

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      router.push('/login');
      return;
    }
    const authUser = getAuthUser();
    setUser(authUser);

    fetchWithAuth('/api/auth/me')
      .then(res => res.json())
      .then(data => {
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data));
      })
      .catch(err => console.error("Erreur récup user:", err));

    fetchWorkouts(athleteId);
    fetchCurrentPlan(athleteId);
    checkGarminStatus();
  }, [router, athleteId]);

  const checkGarminStatus = async () => {
    try {
      const response = await fetchWithAuth('/api/auth/garmin/status');
      if (response.ok) {
        const data = await response.json();
        setGarminStatus(data);
      }
    } catch (err) {
      console.error('Failed to check Garmin status:', err);
    }
  };

  const fetchUserData = async () => {
    try {
      const response = await fetchWithAuth('/api/auth/me');
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        localStorage.setItem('user', JSON.stringify(data));
      }
    } catch (err) {
      console.error('Failed to fetch user data:', err);
    }
  };

  const fetchWorkouts = async (id?: string | null) => {
    try {
      const url = id ? `/api/workouts?athlete_id=${id}` : '/api/workouts';
      const response = await fetchWithAuth(url);
      if (response.ok) {
        const data = await response.json();
        setWorkouts(data);
      }
    } catch (error) {
      console.error('Failed to fetch workouts:', error);
    }
  };

  const fetchCurrentPlan = async (id?: string | null) => {
    try {
      const url = id ? `/api/plans/current?athlete_id=${id}` : '/api/plans/current';
      const response = await fetchWithAuth(url);
      if (response.ok) {
        const data = await response.json();
        setCurrentPlan(data);
      }
    } catch (error) {
      console.error('Failed to fetch plan:', error);
    }
  };

  const handleLogout = () => {
    clearAuthToken();
    router.push('/login');
  };

  const handleDeletePlan = async () => {
    if (!currentPlan) return;
    const msg = athleteId 
      ? "Êtes-vous sûr de vouloir supprimer le plan d'entraînement actif de cet athlète ? Toutes les séances non validées seront supprimées."
      : "Êtes-vous sûr de vouloir supprimer votre plan d'entraînement actif ? Toutes les séances non validées seront supprimées.";
    
    if (!confirm(msg)) return;
    
    try {
      const response = await fetchWithAuth(`/api/plans/${currentPlan.id}`, {
        method: 'DELETE'
      });
      
      if (response.ok) {
        setCurrentPlan(null);
        fetchWorkouts(athleteId);
      } else {
        alert("Erreur lors de la suppression du plan");
      }
    } catch (error) {
      console.error("Error deleting plan:", error);
    }
  };

  const calculateWeeklyLoad = () => {
    const weekStart = startOfWeek(currentDate, { weekStartsOn: 1 });
    const weekEnd = endOfWeek(currentDate, { weekStartsOn: 1 });
    const weekWorkouts = (Array.isArray(workouts) ? workouts : []).filter(w => {
      const d = parseISO(w.date);
      return d >= weekStart && d <= weekEnd;
    });
    return weekWorkouts.reduce((sum, w) => sum + (w.estimated_load || 0), 0);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const {active, over} = event;
    
    if (over) {
      const workout = active.data.current?.workout;
      const newDate = new Date(over.id as string);
      if (workout && !isSameDay(parseISO(workout.date), newDate)) {
        shiftWorkout(workout, newDate);
      }
    }
  };

  const next = () => {
    if (view === 'month') setCurrentDate(addMonths(currentDate, 1));
    else setCurrentDate(addWeeks(currentDate, 1));
  };

  const prev = () => {
    if (view === 'month') setCurrentDate(subMonths(currentDate, 1));
    else setCurrentDate(subWeeks(currentDate, 1));
  };

  const handleWorkoutClick = (workout: Workout) => {
    setSelectedWorkout(workout);
    setIsSideMenuOpen(true);
  };

  const shiftWorkout = async (workout: Workout, newDate: Date) => {
    try {
      const response = await fetchWithAuth(`/api/workouts/${workout.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ date: format(newDate, "yyyy-MM-dd'T'HH:mm:ss") }),
      });
      if (response.ok) {
        fetchWorkouts(athleteId);
        if (selectedWorkout?.id === workout.id) {
          const updated = await response.json();
          setSelectedWorkout(updated);
        }
      }
    } catch (error) {
      console.error('Failed to shift workout:', error);
    }
  };

  const renderHeader = () => (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-6 md:mb-12 bg-white p-6 md:p-8 rounded-[2.5rem] shadow-xl shadow-brand-primary/5 border border-brand-light">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl md:text-5xl font-black text-brand-dark tracking-tighter uppercase leading-none flex items-center gap-3 md:gap-4">
          {format(currentDate, 'MMMM yyyy', { locale: fr })}
          {athleteId && (
            <span className="text-brand-primary text-xs md:text-2xl bg-brand-surface px-2 md:px-4 py-1 rounded-2xl border border-brand-light animate-pulse">
              Vue Athlète
            </span>
          )}
        </h1>
        <div className="flex items-center gap-2 text-brand-secondary font-bold uppercase text-[10px] md:text-xs tracking-widest">
          <CalendarIcon className="w-4 h-4" />
          <span>Tableau de Bord Entraînement</span>
        </div>
      </div>
      
      <div className="flex flex-wrap items-center gap-3 md:gap-4">
        {user?.role === 'coach' && (
          <Link
            href="/coach"
            className="flex items-center gap-2 bg-brand-primary text-white px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-brand-dark transition-all shadow-lg shadow-brand-primary/20"
          >
            <Users className="w-4 h-4" />
            <span>Vue Entraîneur</span>
          </Link>
        )}

        {currentPlan ? (
          <div className="flex items-center gap-3 md:gap-4">
            <div className="flex items-center gap-2 bg-emerald-50 text-emerald-700 px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest border border-emerald-100">
              <CheckCircle2 className="w-4 h-4" />
              <span>Plan: {currentPlan.race_name}</span>
            </div>
            <button
              onClick={handleDeletePlan}
              className="flex items-center gap-2 bg-rose-50 text-rose-600 px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-rose-100 transition-all border border-rose-100"
              title="Supprimer le plan"
            >
              <X className="w-4 h-4" />
              <span>Supprimer</span>
            </button>
          </div>
        ) : (
          <Link
            href={athleteId ? `/plans/new?athleteId=${athleteId}` : "/plans/new"}
            className="flex items-center gap-2 bg-brand-dark text-white px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-brand-primary transition-all shadow-lg shadow-brand-dark/20"
          >
            <Plus className="w-4 h-4" />
            <span>Créer un Plan</span>
          </Link>
        )}

        <Link
          href={athleteId ? `/workouts/new?athleteId=${athleteId}` : "/workouts/new"}
          className="flex items-center gap-2 bg-white text-brand-dark px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-brand-surface transition-all border-2 border-brand-dark shadow-sm"
          title="Ajouter une séance manuellement"
        >
          <Plus className="w-4 h-4" />
          <span>Séance Manuelle</span>
        </Link>

        <button
          onClick={() => setShowGarminAuthModal(true)}
          className={`flex items-center gap-2 px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest transition-all shadow-sm border ${
            garminStatus.is_connected 
            ? 'bg-brand-surface text-brand-primary border-brand-light hover:bg-brand-light' 
            : 'bg-slate-50 text-slate-500 border-slate-100 hover:bg-slate-100'
          }`}
          title="Réglages Garmin Connect"
        >
          <Watch className={`w-4 h-4 ${garminStatus.is_connected ? 'text-brand-primary' : ''}`} />
          <span>Garmin</span>
        </button>
        <button
          onClick={() => setShowStatsModal(true)}
          className={`flex items-center gap-2 px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest transition-all shadow-sm border ${
            user?.vma || user?.ftp
            ? 'bg-brand-surface text-brand-primary border-brand-light hover:bg-brand-light' 
            : 'bg-slate-50 text-slate-500 border-slate-100 hover:bg-slate-100'
          }`}
          title="Statistiques de performance"
        >
          <Zap className={`w-4 h-4 ${user?.vma || user?.ftp ? 'text-brand-primary' : ''}`} />
          <span>Profil</span>
        </button>

        <button
          onClick={handleLogout}
          className="flex items-center gap-2 bg-slate-50 text-slate-500 px-4 md:px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-rose-50 hover:text-rose-600 transition-all border border-slate-100"
        >
          <LogOut className="w-4 h-4" />
          <span>Déconnexion</span>
        </button>

        <div className="flex items-center bg-brand-surface rounded-2xl p-1.5 border border-brand-light shadow-inner">
          <button 
            onClick={() => setView('month')}
            className={`px-4 md:px-6 py-2 rounded-xl text-xs md:text-sm font-black transition-all ${view === 'month' ? 'bg-brand-dark text-white shadow-md' : 'text-brand-secondary hover:text-brand-primary'}`}
          >
            MOIS
          </button>
          <button 
            onClick={() => setView('week')}
            className={`px-4 md:px-6 py-2 rounded-xl text-xs md:text-sm font-black transition-all ${view === 'week' ? 'bg-brand-dark text-white shadow-md' : 'text-brand-secondary hover:text-brand-primary'}`}
          >
            SEMAINE
          </button>
        </div>

        <div className="flex items-center gap-2 bg-white rounded-2xl p-1.5 border border-brand-light shadow-sm">
          <button onClick={prev} className="p-2 hover:bg-brand-surface text-brand-primary rounded-xl transition-colors">
            <ChevronLeft className="w-5 h-5 md:w-6 md:h-6" />
          </button>
          <button 
            onClick={() => setCurrentDate(new Date())}
            className="px-3 md:px-4 py-2 hover:bg-brand-surface rounded-xl text-[10px] md:text-xs font-black uppercase tracking-wider text-brand-dark"
          >
            Aujourd'hui
          </button>
          <button onClick={next} className="p-2 hover:bg-brand-surface text-brand-primary rounded-xl transition-colors">
            <ChevronRight className="w-5 h-5 md:w-6 md:h-6" />
          </button>
        </div>
      </div>
      
      {view === 'week' && (
        <div className="mt-6 md:mt-8 flex items-center gap-3 md:gap-4 bg-brand-dark text-white px-4 md:px-8 py-4 md:py-6 rounded-2xl md:rounded-[2rem] shadow-2xl w-fit border border-brand-primary/30 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-brand-primary/10 rounded-bl-[5rem] -mr-8 -mt-8 transition-transform group-hover:scale-110" />
          <div className="flex items-center gap-3 md:gap-4 border-r border-white/20 pr-4 md:pr-6 relative z-10">
            <Activity className="w-5 h-5 md:w-8 md:h-8 text-brand-accent animate-pulse" />
            <div>
              <div className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-60">Charge Hebdomadaire</div>
              <div className="text-xl md:text-3xl font-black tracking-tighter text-white">{calculateWeeklyLoad().toFixed(0)}</div>
            </div>
          </div>
          <div className="pl-2 relative z-10">
            <div className="text-[9px] md:text-[10px] font-black uppercase tracking-[0.2em] opacity-60">Objectif</div>
            <div className="text-xs md:text-sm font-bold text-brand-secondary">{currentPlan?.race_name || 'Maintien'}</div>
          </div>
        </div>
      )}
    </div>
  );

  const renderDays = () => {
    const days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
    return (
      <div className="grid grid-cols-7 mb-0 bg-brand-dark text-white rounded-t-[2rem] overflow-hidden shadow-lg shadow-brand-dark/10 border-b border-brand-primary/20">
        {days.map(day => (
          <div key={day} className="py-3 md:py-5 text-center text-[9px] md:text-xs font-black uppercase tracking-widest border-r border-white/10 last:border-r-0">
            {day}
          </div>
        ))}
      </div>
    );
  };

  const renderCells = () => {
    const monthStart = startOfMonth(currentDate);
    const monthEnd = endOfMonth(monthStart);
    const startDate = startOfWeek(view === 'month' ? monthStart : currentDate, { weekStartsOn: 1 });
    const endDate = endOfWeek(view === 'month' ? monthEnd : currentDate, { weekStartsOn: 1 });

    const days = eachDayOfInterval({ start: startDate, end: endDate });

    return (
      <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-7 auto-rows-fr border-l border-b border-brand-light overflow-hidden rounded-b-[2rem] shadow-2xl bg-white">
          {days.map((day, idx) => {
            const dayWorkouts = (Array.isArray(workouts) ? workouts : []).filter(w => isSameDay(parseISO(w.date), day));
            const isToday = isSameDay(day, new Date());
            const isNotCurrentMonth = !isSameMonth(day, monthStart) && view === 'month';

            return (
              <DayDroppable 
                key={idx} 
                day={day} 
                isToday={isToday} 
                isNotCurrentMonth={isNotCurrentMonth}
              >
                {dayWorkouts.map(workout => (
                  <DraggableWorkout 
                    key={workout.id} 
                    workout={workout} 
                    onClick={() => handleWorkoutClick(workout)} 
                  />
                ))}
              </DayDroppable>
            );
          })}
        </div>
      </DndContext>
    );
  };

  const renderSideMenu = () => {
    if (!selectedWorkout) return null;

    // Get current week days for shifting
    const weekStart = startOfWeek(parseISO(selectedWorkout.date), { weekStartsOn: 1 });
    const weekDays = eachDayOfInterval({
      start: weekStart,
      end: endOfWeek(weekStart, { weekStartsOn: 1 })
    });

    return (
      <div className={`fixed inset-y-0 right-0 w-full md:w-[450px] bg-white shadow-[-20px_0_50px_rgba(0,0,0,0.1)] transform transition-transform duration-500 ease-in-out z-50 ${isSideMenuOpen ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="p-6 md:p-8 h-full flex flex-col">
          <div className="flex items-center justify-between mb-6 md:mb-10">
            <div className="flex items-center gap-2">
              <div className="w-3 h-8 bg-brand-primary rounded-full shadow-lg shadow-brand-primary/20" />
              <h2 className="text-xl md:text-2xl font-black text-brand-dark uppercase tracking-tighter">Détails</h2>
            </div>
            <button onClick={() => setIsSideMenuOpen(false)} className="p-2 hover:bg-brand-surface rounded-xl transition-colors">
              <X className="w-7 h-7 md:w-8 md:h-8 text-brand-dark" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-6 md:space-y-8 pr-2 custom-scrollbar">
            <div>
              <span className={`inline-block px-4 py-1.5 rounded-full text-[10px] font-black ${TYPE_COLORS[selectedWorkout.workout_type]?.chip || 'bg-brand-surface'} ${TYPE_COLORS[selectedWorkout.workout_type]?.text || 'text-brand-dark'} uppercase tracking-widest mb-4 border ${TYPE_COLORS[selectedWorkout.workout_type]?.bar || 'border-brand-light'}`}>
                {selectedWorkout.workout_type}
              </span>
              <h3 className="text-2xl md:text-4xl font-black text-brand-dark leading-none uppercase tracking-tighter">{selectedWorkout.name}</h3>
              <p className="text-brand-secondary font-bold mt-4 uppercase text-xs tracking-widest">{format(parseISO(selectedWorkout.date), 'EEEE d MMMM yyyy', { locale: fr })}</p>
            </div>

            <div className="grid grid-cols-3 gap-3 md:gap-4">
              <div className="bg-brand-surface border border-brand-light p-3 md:p-5 rounded-2xl md:rounded-3xl">
                <div className="text-brand-secondary text-[9px] md:text-[10px] font-black uppercase tracking-widest mb-2">Durée</div>
                <div className="text-lg md:text-2xl font-black flex items-center gap-2 text-brand-dark">
                  <Clock className="w-4 h-4 text-brand-primary" />
                  {selectedWorkout.duration_minutes}<span className="text-xs">MIN</span>
                </div>
              </div>
              <div className="bg-brand-surface border border-brand-light p-3 md:p-5 rounded-2xl md:rounded-3xl">
                <div className="text-brand-secondary text-[9px] md:text-[10px] font-black uppercase tracking-widest mb-2">Difficulté</div>
                <div className="text-lg md:text-2xl font-black flex items-center gap-2 text-brand-dark">
                  <Activity className="w-4 h-4 text-brand-primary" />
                  {selectedWorkout.difficulty_level}<span className="text-xs">/10</span>
                </div>
              </div>
              <div className="bg-brand-surface border border-brand-light p-3 md:p-5 rounded-2xl md:rounded-3xl">
                <div className="text-brand-secondary text-[9px] md:text-[10px] font-black uppercase tracking-widest mb-2">Charge</div>
                <div className="text-lg md:text-2xl font-black flex items-center gap-2 text-brand-dark">
                  <Dumbbell className="w-4 h-4 text-brand-primary" />
                  {selectedWorkout.estimated_load?.toFixed(0)}
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-black text-xs text-brand-dark uppercase tracking-widest mb-4 flex items-center gap-2">
                <AlignLeft className="w-4 h-4 text-brand-primary" />
                Description
              </h4>
              <p className="text-slate-600 text-sm leading-relaxed font-medium bg-brand-surface p-4 md:p-6 rounded-2xl md:rounded-3xl border border-brand-light italic">
                "{selectedWorkout.description}"
              </p>
            </div>

            {selectedWorkout.is_validated && (
              <div className="bg-emerald-500 text-white rounded-2xl md:rounded-3xl p-4 md:p-6 shadow-xl shadow-emerald-100 border border-emerald-400">
                <div className="flex items-center gap-3 font-black uppercase tracking-widest mb-4">
                  <CheckCircle2 className="w-6 h-6" />
                  Séance Complétée
                </div>
                <div className="space-y-2">
                  <div className="text-sm opacity-90 font-bold">
                    Difficulté ressentie : <span className="text-lg font-black">{selectedWorkout.perceived_difficulty}/10</span>
                  </div>
                  {selectedWorkout.athlete_comment && (
                    <div className="text-sm bg-white/10 p-4 rounded-2xl italic font-medium">
                      "{selectedWorkout.athlete_comment}"
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="mt-6 md:mt-10">
            <Link 
              href={`/workouts/${selectedWorkout.id}`}
              className="w-full flex items-center justify-center gap-3 bg-brand-dark hover:bg-brand-primary text-white font-black uppercase tracking-widest py-4 md:py-5 rounded-2xl transition-all shadow-xl shadow-brand-dark/20 active:scale-[0.98]"
            >
              <ExternalLink className="w-5 h-5" />
              Ouvrir la fiche
            </Link>
          </div>
        </div>
      </div>
    );
  };

  return (
    <main className="min-h-screen bg-brand-surface p-3 md:p-12">
      <div className="max-w-[1600px] mx-auto bg-white rounded-[2rem] md:rounded-[2.5rem] shadow-[0_40px_80px_-20px_rgba(30,58,138,0.1)] overflow-hidden border border-brand-light">
        <div className="p-4 md:p-12">
          {renderHeader()}
          <div className="bg-white rounded-2xl border border-brand-light overflow-hidden shadow-inner bg-slate-50/30">
            {renderDays()}
            {renderCells()}
          </div>
        </div>
      </div>
      
      {renderSideMenu()}
      
      {/* Overlay when side menu is open */}
      {isSideMenuOpen && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-md z-40 transition-opacity duration-500"
          onClick={() => setIsSideMenuOpen(false)}
        />
      )}

      <GarminAuthModal
        isOpen={showGarminAuthModal}
        onClose={() => setShowGarminAuthModal(false)}
        onSuccess={checkGarminStatus}
        currentEmail={garminStatus.garmin_email}
        isConnected={garminStatus.is_connected}
      />

      <MenstrualCycleModal
        isOpen={showMenstrualModal}
        onClose={() => setShowMenstrualModal(false)}
        onSuccess={fetchUserData}
        currentUser={user}
      />

      <AthleteStatsModal
        isOpen={showStatsModal}
        onClose={() => setShowStatsModal(false)}
        onSuccess={fetchUserData}
        currentUser={user}
      />
    </main>
  );
}

export default function CalendarPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center font-black uppercase tracking-widest text-gray-400">Chargement...</div>}>
      <CalendarPageContent />
    </Suspense>
  );
}

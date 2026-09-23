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
  AlignLeft,
  Plus,
  LogOut,
  Users,
  Dumbbell
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
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
} from '@dnd-kit/core';

function DraggableWorkout({ workout, onClick }: { workout: Workout, onClick: () => void }) {
  const {attributes, listeners, setNodeRef, transform} = useDraggable({
    id: `workout-${workout.id}`,
    data: { workout }
  });
  
  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    zIndex: 100,
  } : undefined;

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
      className={`p-3 rounded-xl cursor-grab active:cursor-grabbing text-xs border-2 transition-all hover:scale-[1.02] hover:shadow-xl active:scale-[0.98] ${
        workout.is_validated 
          ? 'bg-white border-green-500 text-black' 
          : 'bg-black border-black text-white'
      }`}
    >
      <div className="font-black uppercase tracking-tighter flex items-center justify-between mb-1">
        <span className="truncate">{workout.workout_type}</span>
        {workout.is_validated && <CheckCircle2 className="w-3 h-3 text-green-500" />}
      </div>
      <div className={`truncate font-bold opacity-80 ${workout.is_validated ? 'text-gray-600' : 'text-gray-300'}`}>
        {workout.name}
      </div>
      <div className="flex items-center gap-1 mt-2 font-black uppercase text-[9px] tracking-widest">
        <Clock className="w-3 h-3" />
        {workout.duration_minutes} MIN
      </div>
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
      className={`min-h-[160px] p-3 border-r border-t border-gray-200 transition-all ${
        isNotCurrentMonth ? 'bg-gray-50/50 text-gray-300' : 'bg-white'
      } ${isToday ? 'bg-yellow-50/50' : ''} ${isOver ? 'bg-blue-50 ring-2 ring-blue-200 ring-inset shadow-inner' : ''}`}
    >
      <div className="flex justify-between items-start mb-2">
        <span className={`text-sm font-black tracking-tighter ${
          isToday 
            ? 'bg-black text-white w-8 h-8 flex items-center justify-center rounded-lg shadow-lg' 
            : isNotCurrentMonth ? 'text-gray-300' : 'text-gray-400'
        }`}>
          {format(day, 'd')}
        </span>
      </div>
      <div className="space-y-2">
        {children}
      </div>
    </div>
  );
}

function CalendarPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const athleteId = searchParams.get('athleteId');
  
  const [user, setUser] = useState<any>(null);
  const [currentDate, setCurrentDate] = useState(new Date());
  const [view, setView] = useState<'month' | 'week'>('month');
  const [workouts, setWorkouts] = useState<Workout[]>([]);
  const [selectedWorkout, setSelectedWorkout] = useState<Workout | null>(null);
  const [isSideMenuOpen, setIsSideMenuOpen] = useState(false);
  const [currentPlan, setCurrentPlan] = useState<any>(null);

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
    fetchWorkouts(athleteId);
    fetchCurrentPlan(athleteId);
  }, [router, athleteId]);

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
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-12">
      <div className="flex flex-col gap-2">
        <h1 className="text-5xl font-black text-black tracking-tighter uppercase leading-none flex items-center gap-4">
          {format(currentDate, 'MMMM yyyy', { locale: fr })}
          {athleteId && (
            <span className="text-blue-600 text-2xl bg-blue-50 px-4 py-1 rounded-2xl border border-blue-100">
              Vue Athlète
            </span>
          )}
        </h1>
        <div className="flex items-center gap-2 text-gray-400 font-bold uppercase text-xs tracking-widest">
          <CalendarIcon className="w-4 h-4" />
          <span>Tableau de Bord Entraînement</span>
        </div>
      </div>
      
      <div className="flex flex-wrap items-center gap-4">
        {user?.role === 'coach' && (
          <Link
            href="/coach"
            className="flex items-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-blue-700 transition-all shadow-lg shadow-blue-200"
          >
            <Users className="w-4 h-4" />
            <span>Vue Entraîneur</span>
          </Link>
        )}

        {currentPlan ? (
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-green-50 text-green-700 px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest border border-green-100">
              <CheckCircle2 className="w-4 h-4" />
              <span>Plan: {currentPlan.race_name}</span>
            </div>
            <button
              onClick={handleDeletePlan}
              className="flex items-center gap-2 bg-red-50 text-red-600 px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-red-100 transition-all border border-red-100"
              title="Supprimer le plan"
            >
              <X className="w-4 h-4" />
              <span>Supprimer</span>
            </button>
          </div>
        ) : (
          <Link
            href={athleteId ? `/plans/new?athleteId=${athleteId}` : "/plans/new"}
            className="flex items-center gap-2 bg-black text-white px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-800 transition-all shadow-lg shadow-gray-200"
          >
            <Plus className="w-4 h-4" />
            <span>Créer un Plan</span>
          </Link>
        )}

        <Link
          href="/workouts/new"
          className="group flex items-center gap-2 bg-white text-black px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-50 transition-all border-2 border-black relative"
          title="Ajouter une séance manuellement"
        >
          <Plus className="w-4 h-4" />
          <span>Séance Manuelle</span>
          {/* Tooltip on hover */}
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1 bg-black text-white text-[10px] rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Ajouter une séance manuellement
          </div>
        </Link>

        <button
          onClick={handleLogout}
          className="flex items-center gap-2 bg-gray-100 text-gray-600 px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-200 transition-all"
        >
          <LogOut className="w-4 h-4" />
          <span>Déconnexion</span>
        </button>

        <div className="flex items-center bg-gray-100 rounded-2xl p-1.5 border border-gray-200">
          <button 
            onClick={() => setView('month')}
            className={`px-6 py-2 rounded-xl text-sm font-black transition-all ${view === 'month' ? 'bg-black text-white shadow-lg' : 'text-gray-500 hover:text-black'}`}
          >
            MOIS
          </button>
          <button 
            onClick={() => setView('week')}
            className={`px-6 py-2 rounded-xl text-sm font-black transition-all ${view === 'week' ? 'bg-black text-white shadow-lg' : 'text-gray-500 hover:text-black'}`}
          >
            SEMAINE
          </button>
        </div>

        <div className="flex items-center gap-2 bg-white rounded-2xl p-1.5 border border-gray-200">
          <button onClick={prev} className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
            <ChevronLeft className="w-6 h-6" />
          </button>
          <button 
            onClick={() => setCurrentDate(new Date())}
            className="px-4 py-2 hover:bg-gray-100 rounded-xl text-xs font-black uppercase tracking-wider"
          >
            Aujourd'hui
          </button>
          <button onClick={next} className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>
      </div>
      
      {view === 'week' && (
        <div className="mt-8 flex items-center gap-4 bg-black text-white px-8 py-6 rounded-[2rem] shadow-2xl w-fit">
          <div className="flex items-center gap-4 border-r border-white/20 pr-6">
            <Activity className="w-8 h-8 text-yellow-400" />
            <div>
              <div className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60">Charge Hebdomadaire</div>
              <div className="text-3xl font-black tracking-tighter">{calculateWeeklyLoad().toFixed(0)}</div>
            </div>
          </div>
          <div className="pl-2">
            <div className="text-[10px] font-black uppercase tracking-[0.2em] opacity-60">Objectif</div>
            <div className="text-sm font-bold opacity-80">{currentPlan?.race_name || 'Maintien'}</div>
          </div>
        </div>
      )}
    </div>
  );

  const renderDays = () => {
    const days = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
    return (
      <div className="grid grid-cols-7 mb-0 bg-black text-white rounded-t-2xl">
        {days.map(day => (
          <div key={day} className="py-4 text-center text-xs font-black uppercase tracking-widest border-r border-white/10 last:border-r-0">
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
        <div className="grid grid-cols-7 auto-rows-fr border-l border-b border-gray-200">
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
        <div className="p-8 h-full flex flex-col">
          <div className="flex items-center justify-between mb-10">
            <div className="flex items-center gap-2">
              <div className="w-3 h-8 bg-black rounded-full" />
              <h2 className="text-2xl font-black text-black uppercase tracking-tighter">Détails</h2>
            </div>
            <button onClick={() => setIsSideMenuOpen(false)} className="p-2 hover:bg-gray-100 rounded-xl transition-colors">
              <X className="w-8 h-8 text-black" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-8 pr-2 custom-scrollbar">
            <div>
              <span className="inline-block px-4 py-1.5 rounded-full text-[10px] font-black bg-yellow-400 text-black uppercase tracking-widest mb-4">
                {selectedWorkout.workout_type}
              </span>
              <h3 className="text-4xl font-black text-black leading-none uppercase tracking-tighter">{selectedWorkout.name}</h3>
              <p className="text-gray-400 font-bold mt-4 uppercase text-xs tracking-widest">{format(parseISO(selectedWorkout.date), 'EEEE d MMMM yyyy', { locale: fr })}</p>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <div className="bg-gray-50 border border-gray-100 p-5 rounded-3xl">
                <div className="text-gray-400 text-[10px] font-black uppercase tracking-widest mb-2">Durée</div>
                <div className="text-2xl font-black flex items-center gap-2">
                  <Clock className="w-5 h-5 text-black" />
                  {selectedWorkout.duration_minutes}<span className="text-sm">MIN</span>
                </div>
              </div>
              <div className="bg-gray-50 border border-gray-100 p-5 rounded-3xl">
                <div className="text-gray-400 text-[10px] font-black uppercase tracking-widest mb-2">Difficulté</div>
                <div className="text-2xl font-black flex items-center gap-2">
                  <Activity className="w-5 h-5 text-black" />
                  {selectedWorkout.difficulty_level}<span className="text-sm">/10</span>
                </div>
              </div>
              <div className="bg-gray-50 border border-gray-100 p-5 rounded-3xl">
                <div className="text-gray-400 text-[10px] font-black uppercase tracking-widest mb-2">Charge</div>
                <div className="text-2xl font-black flex items-center gap-2">
                  <Dumbbell className="w-5 h-5 text-black" />
                  {selectedWorkout.estimated_load?.toFixed(0)}
                </div>
              </div>
            </div>

            <div>
              <h4 className="font-black text-xs text-black uppercase tracking-widest mb-4 flex items-center gap-2">
                <AlignLeft className="w-4 h-4" />
                Description
              </h4>
              <p className="text-gray-600 text-sm leading-relaxed font-medium bg-gray-50 p-6 rounded-3xl border border-gray-100 italic">
                "{selectedWorkout.description}"
              </p>
            </div>

            {selectedWorkout.is_validated && (
              <div className="bg-green-500 text-white rounded-3xl p-6 shadow-xl shadow-green-100">
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

          <div className="mt-10">
            <Link 
              href={`/workouts/${selectedWorkout.id}`}
              className="w-full flex items-center justify-center gap-3 bg-black hover:bg-gray-900 text-white font-black uppercase tracking-widest py-5 rounded-2xl transition-all shadow-2xl active:scale-[0.98]"
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
    <main className="min-h-screen bg-[#F8F9FA] p-4 md:p-12">
      <div className="max-w-[1600px] mx-auto bg-white rounded-[2.5rem] shadow-[0_40px_80px_-20px_rgba(0,0,0,0.08)] overflow-hidden border border-gray-100">
        <div className="p-6 md:p-12">
          {renderHeader()}
          <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm">
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

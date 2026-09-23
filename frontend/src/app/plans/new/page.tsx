'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { 
  ChevronLeft, 
  Save, 
  X, 
  AlertTriangle,
  Calendar as CalendarIcon,
  Timer,
  Trophy,
  Dumbbell,
  Plus
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';
import { fetchWithAuth } from '@/lib/api';
import {
  DndContext,
  DragEndEvent,
  useDraggable,
  useDroppable,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';

const GOAL_TYPES = ['plaisir', 'maintien', 'mixte', 'intensité', 'trail'];
const DAYS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];

const DEFAULT_ASSIGNMENTS: Record<string, Record<number, Record<number, string>>> = {
  "plaisir": {
    1: { 2: "Libre" },
    2: { 2: "Endurance", 5: "Libre" },
    3: { 1: "Endurance", 3: "Libre", 5: "Sortie longue" },
    4: { 1: "Libre", 3: "Endurance", 5: "Libre", 6: "Sortie longue" },
    5: { 0: "Endurance", 1: "Libre", 3: "Endurance", 5: "Libre", 6: "Sortie longue" },
    6: { 1: "Libre", 2: "Endurance", 3: "Libre", 4: "Endurance", 5: "Libre", 6: "Sortie longue" },
    7: { 0: "Endurance", 1: "Libre", 2: "Endurance", 3: "Libre", 4: "Endurance", 5: "Libre", 6: "Sortie longue" },
  },
  "maintien": {
    1: { 2: "Endurance" },
    2: { 2: "Endurance", 5: "Fractionné" },
    3: { 1: "Endurance", 3: "Fractionné", 5: "Sortie longue" },
    4: { 1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: "Sortie longue" },
    5: { 0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Libre", 6: "Sortie longue" },
    6: { 1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Libre", 5: "Endurance", 6: "Sortie longue" },
    7: { 0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Sortie longue" },
  },
  "mixte": {
    1: { 2: "Endurance" },
    2: { 2: "Endurance", 5: "Fractionné" },
    3: { 1: "Endurance", 3: "Fractionné", 5: "Sortie longue" },
    4: { 1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: "Sortie longue" },
    5: { 0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Sortie longue" },
    6: { 1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Fractionné", 5: "Endurance", 6: "Sortie longue" },
    7: { 0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Sortie longue" },
  },
  "intensité": {
    1: { 2: "Fractionné" },
    2: { 2: "Endurance", 5: "Fractionné" },
    3: { 1: "Endurance", 3: "Fractionné", 5: "Sortie longue" },
    4: { 1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Sortie longue" },
    5: { 0: "Fractionné", 1: "Endurance", 3: "Fractionné", 5: "Libre", 6: "Sortie longue" },
    6: { 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Sortie longue" },
    7: { 0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Fractionné", 6: "Sortie longue" },
  },
  "trail": {
    1: { 2: "Endurance" },
    2: { 2: "Endurance", 5: "Trail" },
    3: { 1: "Endurance", 3: "Fractionné", 5: "Trail" },
    4: { 1: "Endurance", 3: "Fractionné", 5: "Endurance", 6: "Trail" },
    5: { 0: "Endurance", 1: "Fractionné", 3: "Endurance", 5: "Fractionné", 6: "Trail" },
    6: { 1: "Endurance", 2: "Fractionné", 3: "Endurance", 4: "Fractionné", 5: "Endurance", 6: "Trail" },
    7: { 0: "Endurance", 1: "Fractionné", 2: "Endurance", 3: "Fractionné", 4: "Endurance", 5: "Libre", 6: "Trail" },
  }
};

function DraggableDayWorkout({ type, dayIdx }: { type: string, dayIdx: number }) {
  const {attributes, listeners, setNodeRef, transform, isDragging} = useDraggable({
    id: `day-workout-${dayIdx}`,
    data: { type, fromDayIdx: dayIdx }
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
      className={`bg-black text-white px-3 py-2 rounded-lg text-[9px] font-black uppercase tracking-tighter w-full text-center relative cursor-grab active:cursor-grabbing hover:bg-gray-800 transition-all shadow-md ${isDragging ? 'opacity-50' : ''}`}
    >
      {type}
    </div>
  );
}

function DaySlot({ dayIdx, type }: { dayIdx: number, type: string | null }) {
  const {setNodeRef, isOver} = useDroppable({
    id: `day-${dayIdx}`,
    data: { dayIdx }
  });

  return (
    <div 
      ref={setNodeRef}
      className={`relative min-h-[100px] rounded-2xl border-2 border-dashed flex flex-col items-center justify-center p-2 transition-all ${
        isOver ? 'bg-blue-50 border-blue-400 border-solid scale-105' : 
        type ? 'bg-white border-black border-solid shadow-sm' : 'bg-gray-50 border-gray-200 hover:border-gray-300'
      }`}
    >
      <span className="text-[9px] font-black uppercase tracking-widest text-gray-400 mb-2">{DAYS[dayIdx].slice(0, 3)}</span>
      {type && (
        <DraggableDayWorkout type={type} dayIdx={dayIdx} />
      )}
      {!type && <Plus className="w-4 h-4 text-gray-200" />}
    </div>
  );
}

function NewPlanPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const athleteId = searchParams.get('athleteId');
  
  const [loading, setLoading] = useState(false);
  const [showPopup, setShowPopup] = useState(false);
  const [existingPlan, setExistingPlan] = useState<any>(null);
  const [cancellationComment, setCancellationComment] = useState('');
  
  const [formData, setFormData] = useState({
    race_name: '',
    race_date: '',
    race_distance: 10,
    race_estimated_time: '',
    start_date: '',
    sessions_per_week: 3,
    goal_type: 'maintien',
    training_days: {} as Record<number, string>,
    estimated_vma: 5.0 // 5:00/km par défaut
  });

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  useEffect(() => {
    // Set default start_date to next Monday
    const now = new Date();
    const day = now.getDay();
    const diff = (day === 0 ? 1 : 8 - day);
    const nextMonday = new Date(now);
    nextMonday.setDate(now.getDate() + (day === 1 ? 0 : diff));
    setFormData(prev => ({...prev, start_date: nextMonday.toISOString().split('T')[0]}));
  }, []);

  // Update training days automatically when goal or sessions per week change
  useEffect(() => {
    const defaults = DEFAULT_ASSIGNMENTS[formData.goal_type]?.[formData.sessions_per_week];
    if (defaults) {
      setFormData(prev => ({
        ...prev,
        training_days: { ...defaults }
      }));
    }
  }, [formData.goal_type, formData.sessions_per_week]);

  const handleStartDateChange = (dateStr: string) => {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return;
    
    if (date.getDay() !== 1) {
      alert("Le plan doit impérativement commencer un lundi. La date va être ajustée.");
      const day = date.getDay();
      const diff = (day === 0 ? 1 : 8 - day);
      const nextMonday = new Date(date);
      nextMonday.setDate(date.getDate() + (day === 1 ? 0 : diff));
      setFormData({...formData, start_date: nextMonday.toISOString().split('T')[0]});
    } else {
      setFormData({...formData, start_date: dateStr});
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const {active, over} = event;
    
    if (over) {
      const fromDayIdx = active.data.current?.fromDayIdx;
      const toDayIdx = over.data.current?.dayIdx;
      const type = active.data.current?.type;
      
      if (fromDayIdx !== undefined && toDayIdx !== undefined && fromDayIdx !== toDayIdx) {
        setFormData(prev => {
          const newDays = {...prev.training_days};
          const targetType = newDays[toDayIdx];
          
          // Swap if there is already a workout at target, otherwise just move
          newDays[toDayIdx] = type;
          if (targetType) {
            newDays[fromDayIdx] = targetType;
          } else {
            delete newDays[fromDayIdx];
          }
          
          return {...prev, training_days: newDays};
        });
      }
    }
  };

  const removeDay = (dayIdx: number) => {
    setFormData(prev => {
      const newDays = {...prev.training_days};
      delete newDays[dayIdx];
      return {...prev, training_days: newDays};
    });
  };

  useEffect(() => {
    const checkExistingPlan = async () => {
      const url = athleteId ? `/api/plans/current?athlete_id=${athleteId}` : '/api/plans/current';
      const res = await fetchWithAuth(url);
      if (res.ok) {
        const data = await res.json();
        if (data) {
          setExistingPlan(data);
          setShowPopup(true);
        }
      }
    };
    checkExistingPlan();
  }, [athleteId]);

  const handleArchive = async () => {
    if (!cancellationComment) {
      alert('Veuillez entrer un commentaire pour l\'annulation.');
      return;
    }
    setLoading(true);
    try {
      const res = await fetchWithAuth(`/api/plans/${existingPlan.id}/archive`, {
        method: 'POST',
        body: JSON.stringify({ cancellation_comment: cancellationComment })
      });
      if (res.ok) {
        setShowPopup(false);
        setExistingPlan(null);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetchWithAuth('/api/plans', {
        method: 'POST',
        body: JSON.stringify({
          ...formData,
          athlete_id: athleteId ? parseInt(athleteId) : null,
          race_date: format(new Date(formData.race_date), "yyyy-MM-dd'T'12:00:00"),
          start_date: format(new Date(formData.start_date), "yyyy-MM-dd'T'00:00:00"),
        })
      });
      if (res.ok) {
        router.push(athleteId ? `/?athleteId=${athleteId}` : '/');
      } else {
        const err = await res.json();
        alert(err.detail || 'Erreur lors de la création du plan');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };


  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      {/* Popup Overlay */}
      {showPopup && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-[2.5rem] p-10 max-w-lg w-full shadow-2xl border border-gray-100">
            <div className="flex flex-col items-center text-center">
              <div className="bg-amber-100 p-4 rounded-3xl mb-6">
                <AlertTriangle className="w-10 h-10 text-amber-600" />
              </div>
              <h3 className="text-3xl font-black text-black uppercase tracking-tight mb-2">Plan en cours</h3>
              <p className="text-gray-500 font-medium mb-8">
                Vous avez déjà un plan d'entraînement actif ({existingPlan?.race_name}). Voulez-vous l'annuler pour en créer un nouveau ?
              </p>
              
              <div className="w-full space-y-4">
                <textarea
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold text-black text-sm"
                  placeholder="Raison de l'annulation..."
                  rows={3}
                  value={cancellationComment}
                  onChange={(e) => setCancellationComment(e.target.value)}
                />
                
                <div className="flex gap-4">
                  <button
                    onClick={() => router.push('/')}
                    className="flex-1 py-4 px-6 rounded-2xl font-black uppercase text-xs tracking-widest bg-gray-100 text-gray-500 hover:bg-gray-200 transition-all"
                  >
                    Revenir en arrière
                  </button>
                  <button
                    onClick={handleArchive}
                    disabled={loading}
                    className="flex-1 py-4 px-6 rounded-2xl font-black uppercase text-xs tracking-widest bg-black text-white hover:bg-gray-800 transition-all shadow-lg"
                  >
                    {loading ? 'Validation...' : 'Valider'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-30 px-6 py-6">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <Link href={athleteId ? `/?athleteId=${athleteId}` : "/"} className="flex items-center gap-2 text-gray-400 hover:text-black transition-colors font-black uppercase text-xs tracking-widest">
            <ChevronLeft className="w-5 h-5" />
            <span>Retour</span>
          </Link>
          <h1 className="text-2xl font-black text-black uppercase tracking-tighter">Nouveau Plan</h1>
          <div className="w-20" />
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 mt-12">
        <form onSubmit={handleSubmit} className="space-y-8">
          {/* Race Section */}
          <section className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 space-y-6">
            <div className="flex items-center gap-3 mb-2">
              <Trophy className="w-6 h-6 text-black" />
              <h2 className="text-xl font-black uppercase tracking-tight">Votre Objectif</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Nom de la course</label>
                <input
                  type="text"
                  required
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                  placeholder="Ex: Marathon de Paris"
                  value={formData.race_name}
                  onChange={e => setFormData({...formData, race_name: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Date de la course</label>
                <input
                  type="date"
                  required
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                  value={formData.race_date}
                  onChange={e => setFormData({...formData, race_date: e.target.value})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Distance (km)</label>
                <input
                  type="number"
                  required
                  step="0.1"
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                  value={formData.race_distance}
                  onChange={e => setFormData({...formData, race_distance: parseFloat(e.target.value)})}
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Temps estimé (hh:mm:ss)</label>
                <input
                  type="text"
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                  placeholder="03:30:00"
                  value={formData.race_estimated_time}
                  onChange={e => setFormData({...formData, race_estimated_time: e.target.value})}
                />
              </div>
            </div>
          </section>

          {/* Config Section */}
          <section className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 space-y-6">
            <div className="flex items-center gap-3 mb-2">
              <CalendarIcon className="w-6 h-6 text-black" />
              <h2 className="text-xl font-black uppercase tracking-tight">Configuration</h2>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Date de début</label>
                <input
                  type="date"
                  required
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold"
                  value={formData.start_date}
                  onChange={e => handleStartDateChange(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">Séances par semaine</label>
                <select
                  className="w-full px-6 py-4 rounded-2xl bg-gray-50 border-2 border-transparent focus:border-black focus:bg-white outline-none transition-all font-bold appearance-none cursor-pointer"
                  value={formData.sessions_per_week}
                  onChange={e => setFormData({...formData, sessions_per_week: parseInt(e.target.value)})}
                >
                  {[1,2,3,4,5,6,7].map(n => <option key={n} value={n}>{n} séance{n>1?'s':''}</option>)}
                </select>
              </div>
            </div>

            <div className="space-y-4">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1 block">Type de plan</label>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {GOAL_TYPES.map(type => (
                  <button
                    key={type}
                    type="button"
                    onClick={() => setFormData({...formData, goal_type: type})}
                    className={`py-3 px-2 rounded-2xl font-black uppercase text-[10px] tracking-widest transition-all border-2 ${formData.goal_type === type ? 'bg-black text-white border-black shadow-lg' : 'bg-gray-50 text-gray-400 border-transparent hover:border-gray-200'}`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1 block">Jours d'entraînement (Déplacez les séances)</label>
              
              <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
                <div className="space-y-6">
                  {/* Weekly Calendar Drop Zones */}
                  <div className="grid grid-cols-4 md:grid-cols-7 gap-3">
                    {[0, 1, 2, 3, 4, 5, 6].map((idx) => (
                      <DaySlot 
                        key={idx} 
                        dayIdx={idx} 
                        type={formData.training_days[idx] || null} 
                      />
                    ))}
                  </div>
                </div>
              </DndContext>
              
              <p className="text-[10px] text-gray-400 italic font-medium">
                Les types de séances sont fixés par votre objectif. Vous pouvez les déplacer d'un jour à l'autre par drag & drop.
              </p>
            </div>
            
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-400 ml-1">VMA Estimée (min/km)</label>
                <span className="text-sm font-black text-black">{formData.estimated_vma.toFixed(1)} min/km</span>
              </div>
              <input
                type="range"
                min="3"
                max="10"
                step="0.1"
                className="w-full h-2 bg-gray-100 rounded-lg appearance-none cursor-pointer accent-black"
                value={formData.estimated_vma}
                onChange={e => setFormData({...formData, estimated_vma: parseFloat(e.target.value)})}
              />
              <div className="flex justify-between text-[10px] font-bold text-gray-400 px-1">
                <span>Rapide (3.0)</span>
                <span>Lent (10.0)</span>
              </div>
            </div>
          </section>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-6 rounded-[2rem] bg-black text-white font-black uppercase tracking-[0.3em] hover:bg-gray-800 transition-all shadow-xl shadow-gray-200 disabled:opacity-50"
          >
            {loading ? 'Génération du plan...' : 'Générer mon plan'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function NewPlanPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center font-black uppercase tracking-widest text-gray-400">Chargement...</div>}>
      <NewPlanPageContent />
    </Suspense>
  );
}

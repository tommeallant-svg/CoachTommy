'use client';

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  Plus, 
  Trash2, 
  Save,
  Dumbbell,
  Activity,
  Type,
  Layout,
  Clock,
  Zap,
  RotateCcw
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth, getAuthUser } from '@/lib/api';
import { CatalogWorkout, CatalogInterval, CatalogBlock } from '@/types/workout';

export default function CatalogEditPage() {
  const { id } = useParams();
  const router = useRouter();
  const isNew = id === 'new';
  
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [workout, setWorkout] = useState<Partial<CatalogWorkout>>({
    name: '',
    workout_type: 'Fractionné',
    category: 'Fractionné',
    perceived_difficulty: 5,
    scheme: [
      { 
        repetitions: 1, 
        intervals: [{ type: 'Echauffement', duration: 15, pace_vma_min: 65, pace_vma_max: 65 }] 
      },
      { 
        repetitions: 10, 
        intervals: [
          { type: 'Fraction', duration: 1, pace_vma_min: 100, pace_vma_max: 105 },
          { type: 'Récupération', duration: 1, pace_vma_min: 60, pace_vma_max: 60 }
        ] 
      },
      { 
        repetitions: 1, 
        intervals: [{ type: 'Retour calme', duration: 10, pace_vma_min: 65, pace_vma_max: 65 }] 
      }
    ]
  });

  useEffect(() => {
    const user = getAuthUser();
    if (user?.role !== 'coach') {
      router.push('/');
      return;
    }
    if (!isNew) {
      fetchWorkout();
    }
  }, [id]);

  const fetchWorkout = async () => {
    try {
      const res = await fetchWithAuth(`/api/catalog`);
      if (res.ok) {
        const data = await res.json();
        const found = data.find((w: any) => w.id === parseInt(id as string));
        if (found) {
          // Migration legacy structure
          if (found.scheme && found.scheme.length > 0 && !found.scheme[0].intervals) {
            found.scheme = found.scheme.map((i: any) => ({
              repetitions: i.repetitions || 1,
              intervals: [{
                type: i.type,
                duration: i.duration,
                distance: i.distance,
                pace_vma_min: i.pace_vma || 0,
                pace_vma_max: i.pace_vma || 0
              }]
            }));
          }
          setWorkout(found);
        } else {
          router.push('/catalog');
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const addBlock = () => {
    setWorkout({
      ...workout,
      scheme: [...(workout.scheme || []), { repetitions: 1, intervals: [{ type: 'Nouveau', duration: 1, pace_vma_min: 80, pace_vma_max: 85 }] }]
    });
  };

  const removeBlock = (index: number) => {
    const newScheme = [...(workout.scheme || [])];
    newScheme.splice(index, 1);
    setWorkout({ ...workout, scheme: newScheme });
  };

  const updateBlock = (index: number, field: keyof CatalogBlock, value: any) => {
    const newScheme = [...(workout.scheme || [])];
    newScheme[index] = { ...newScheme[index], [field]: value };
    setWorkout({ ...workout, scheme: newScheme });
  };

  const addInterval = (blockIdx: number) => {
    const newScheme = [...(workout.scheme || [])];
    newScheme[blockIdx].intervals.push({ type: 'Nouvel intervalle', duration: 1, pace_vma_min: 80, pace_vma_max: 85 });
    setWorkout({ ...workout, scheme: newScheme });
  };

  const removeInterval = (blockIdx: number, intervalIdx: number) => {
    const newScheme = [...(workout.scheme || [])];
    newScheme[blockIdx].intervals.splice(intervalIdx, 1);
    if (newScheme[blockIdx].intervals.length === 0) {
      newScheme.splice(blockIdx, 1);
    }
    setWorkout({ ...workout, scheme: newScheme });
  };

  const updateInterval = (blockIdx: number, intervalIdx: number, updates: Partial<CatalogInterval>) => {
    const newScheme = [...(workout.scheme || [])];
    newScheme[blockIdx].intervals[intervalIdx] = { ...newScheme[blockIdx].intervals[intervalIdx], ...updates };
    setWorkout({ ...workout, scheme: newScheme });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const url = isNew ? '/api/catalog' : `/api/catalog/${id}`;
      const method = isNew ? 'POST' : 'PATCH';
      const res = await fetchWithAuth(url, {
        method,
        body: JSON.stringify(workout)
      });
      if (res.ok) {
        router.push('/catalog');
      }
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center font-black uppercase text-gray-400 tracking-widest">Chargement...</div>;

  return (
    <div className="min-h-screen bg-[#F8F9FA] pb-20">
      <div className="bg-white border-b border-gray-100 sticky top-0 z-50 px-6 py-6">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <Link href="/catalog" className="flex items-center gap-2 text-gray-400 hover:text-black transition-colors font-black uppercase text-xs tracking-widest">
            <ChevronLeft className="w-5 h-5" />
            <span>Catalogue</span>
          </Link>
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-black text-black uppercase tracking-tighter">
              {isNew ? 'Nouvel Entraînement' : 'Éditer la Séance'}
            </h1>
          </div>
          <button 
            onClick={handleSave} 
            disabled={saving}
            className="flex items-center gap-2 bg-black text-white px-8 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-gray-800 transition-all disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Enregistrement...' : 'Enregistrer'}</span>
          </button>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 mt-12 space-y-12">
        {/* Basic Info Card */}
        <section className="bg-white rounded-[3rem] p-10 shadow-sm border border-gray-100 space-y-8">
          <div className="flex items-center gap-3">
            <div className="bg-yellow-400 p-2 rounded-xl">
              <Type className="w-5 h-5 text-black" />
            </div>
            <h2 className="text-xl font-black text-black uppercase tracking-tight">Informations Générales</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Nom de la séance</label>
              <input 
                type="text" 
                value={workout.name} 
                onChange={e => setWorkout({...workout, name: e.target.value})}
                placeholder="ex: VMA Courte 30/30"
                className="w-full bg-gray-50 border-none rounded-2xl px-6 py-4 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
              />
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Type de séance</label>
              <select 
                value={workout.workout_type} 
                onChange={e => setWorkout({...workout, workout_type: e.target.value})}
                className="w-full bg-gray-50 border-none rounded-2xl px-6 py-4 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all appearance-none"
              >
                <option value="VO2 Max">VO2 Max</option>
                <option value="Seuil">Seuil</option>
                <option value="Tempo">Tempo</option>
                <option value="Fractionné">Fractionné</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Difficulté estimée (1-10)</label>
              <div className="flex items-center gap-4">
                <input 
                  type="range" min="1" max="10" step="1"
                  value={workout.perceived_difficulty} 
                  onChange={e => setWorkout({...workout, perceived_difficulty: parseInt(e.target.value)})}
                  className="flex-1 h-2 bg-gray-100 rounded-full appearance-none cursor-pointer accent-black"
                />
                <span className="w-12 h-12 bg-black text-white rounded-xl flex items-center justify-center font-black">{workout.perceived_difficulty}</span>
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-[10px] font-black uppercase tracking-widest text-gray-400">Catégorie</label>
              <input 
                type="text" 
                value={workout.category} 
                readOnly
                className="w-full bg-gray-100 border-none rounded-2xl px-6 py-4 font-bold text-gray-400 outline-none"
              />
            </div>
          </div>
        </section>

        {/* Scheme Editor */}
        <section className="space-y-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-black p-2 rounded-xl">
                <Layout className="w-5 h-5 text-white" />
              </div>
              <h2 className="text-xl font-black text-black uppercase tracking-tight">Schéma d'entraînement</h2>
            </div>
            <button 
              onClick={addBlock}
              className="flex items-center gap-2 bg-white text-black border border-gray-200 px-6 py-3 rounded-2xl font-black uppercase text-[10px] tracking-widest hover:bg-black hover:text-white transition-all shadow-sm"
            >
              <Plus className="w-4 h-4" />
              Ajouter un bloc
            </button>
          </div>

          <div className="space-y-8">
            {workout.scheme?.map((block, bIdx) => (
              <div key={bIdx} className="bg-white rounded-[2.5rem] p-8 shadow-sm border-2 border-gray-100 relative">
                <div className="flex items-center justify-between mb-8 border-b border-gray-50 pb-6">
                  <div className="flex items-center gap-6">
                    <div className="flex items-center gap-2">
                      <RotateCcw className="w-4 h-4 text-gray-400" />
                      <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">Répétitions du bloc</span>
                    </div>
                    <input 
                      type="number" 
                      value={block.repetitions} 
                      onChange={e => updateBlock(bIdx, 'repetitions', parseInt(e.target.value))}
                      className="w-20 bg-gray-50 border-none rounded-xl px-4 py-2 font-black text-black outline-none focus:ring-2 focus:ring-black transition-all"
                    />
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => addInterval(bIdx)}
                      className="flex items-center gap-2 bg-gray-50 text-gray-600 px-4 py-2 rounded-xl font-black uppercase text-[10px] tracking-widest hover:bg-black hover:text-white transition-all"
                    >
                      <Plus className="w-3 h-3" />
                      Intervalle
                    </button>
                    <button 
                      onClick={() => removeBlock(bIdx)}
                      className="p-2 text-gray-300 hover:text-red-500 transition-all"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>
                </div>

                <div className="space-y-4">
                  {block.intervals.map((interval, iIdx) => (
                    <div key={iIdx} className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end bg-gray-50/50 p-6 rounded-3xl border border-transparent hover:border-gray-200 transition-all">
                      <div className="md:col-span-3 space-y-2">
                        <label className="text-[9px] font-black uppercase tracking-widest text-gray-400">Type</label>
                        <input 
                          type="text" 
                          value={interval.type} 
                          onChange={e => updateInterval(bIdx, iIdx, { type: e.target.value })}
                          className="w-full bg-white border-none rounded-xl px-4 py-3 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
                        />
                      </div>

                      <div className="md:col-span-3 space-y-2">
                        <label className="text-[9px] font-black uppercase tracking-widest text-gray-400 flex items-center gap-1">
                          <Clock className="w-3 h-3" /> Volume
                        </label>
                        <div className="flex items-center gap-2">
                          <input 
                            type="number" step="0.5"
                            value={interval.duration || interval.distance} 
                            onChange={e => updateInterval(bIdx, iIdx, interval.duration !== undefined ? { duration: parseFloat(e.target.value) } : { distance: parseFloat(e.target.value) })}
                            className="w-full bg-white border-none rounded-xl px-4 py-3 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
                          />
                          <button 
                            onClick={() => {
                              if (interval.duration !== undefined) {
                                updateInterval(bIdx, iIdx, { distance: interval.duration, duration: undefined });
                              } else {
                                updateInterval(bIdx, iIdx, { duration: interval.distance, distance: undefined });
                              }
                            }}
                            className="bg-white border border-gray-100 px-3 py-3 rounded-xl text-[10px] font-black uppercase hover:bg-gray-100 transition-all"
                          >
                            {interval.duration !== undefined ? 'MIN' : 'M'}
                          </button>
                        </div>
                      </div>

                      <div className="md:col-span-5 space-y-2">
                        <label className="text-[9px] font-black uppercase tracking-widest text-gray-400 flex items-center gap-1">
                          <Zap className="w-3 h-3" /> Allure (% VMA Min / Max)
                        </label>
                        <div className="flex items-center gap-2">
                          <input 
                            type="number" 
                            value={interval.pace_vma_min} 
                            onChange={e => updateInterval(bIdx, iIdx, { pace_vma_min: parseInt(e.target.value) })}
                            className="w-full bg-white border-none rounded-xl px-4 py-3 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
                            placeholder="Min"
                          />
                          <span className="text-gray-300 font-black">-</span>
                          <input 
                            type="number" 
                            value={interval.pace_vma_max} 
                            onChange={e => updateInterval(bIdx, iIdx, { pace_vma_max: parseInt(e.target.value) })}
                            className="w-full bg-white border-none rounded-xl px-4 py-3 font-bold text-black outline-none focus:ring-2 focus:ring-black transition-all"
                            placeholder="Max"
                          />
                          <span className="font-black text-gray-400">%</span>
                        </div>
                      </div>

                      <div className="md:col-span-1 flex justify-end pb-1">
                        <button 
                          onClick={() => removeInterval(bIdx, iIdx)}
                          className="p-3 text-gray-300 hover:text-red-500 transition-all"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

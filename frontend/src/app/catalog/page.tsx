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
  Tag
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth, getAuthUser } from '@/lib/api';

export default function CatalogPage() {
  const router = useRouter();
  const [workouts, setWorkouts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<any>(null);

  useEffect(() => {
    const user = getAuthUser();
    if (user?.role !== 'coach') {
      router.push('/');
      return;
    }
    fetchCatalog();
  }, [router]);

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
    </div>
  );
}

'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { 
  ChevronLeft, 
  Users, 
  Search, 
  ExternalLink, 
  Pencil, 
  BookOpen, 
  TrendingUp,
  Calendar,
  CheckCircle2
} from 'lucide-react';
import Link from 'next/link';
import { fetchWithAuth, getAuthUser } from '@/lib/api';

export default function CoachPage() {
  const router = useRouter();
  const [athletes, setAthletes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const user = getAuthUser();
    if (user?.role !== 'coach') {
      router.push('/');
      return;
    }
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
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-surface pb-20">
      <div className="bg-brand-dark border-b border-brand-primary/20 sticky top-0 z-30 px-6 py-6 shadow-lg shadow-brand-dark/10">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-brand-secondary hover:text-white transition-colors font-black uppercase text-xs tracking-widest">
            <ChevronLeft className="w-5 h-5" />
            <span>Tableau de bord</span>
          </Link>
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-black text-white uppercase tracking-tighter">Espace Entraîneur</h1>
          </div>
          <div className="flex gap-4">
            <Link href="/catalog" className="flex items-center gap-2 bg-brand-primary text-white px-6 py-3 rounded-2xl font-black uppercase text-xs tracking-widest hover:bg-brand-secondary transition-all shadow-md">
              <BookOpen className="w-4 h-4" />
              <span>Catalogue</span>
            </Link>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 mt-12 space-y-8">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-brand-accent p-3 rounded-2xl shadow-lg shadow-brand-accent/20 text-white">
              <Users className="w-6 h-6" />
            </div>
            <h2 className="text-2xl font-black text-brand-dark uppercase tracking-tight">Mes Athlètes</h2>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-20 font-black uppercase text-brand-secondary tracking-widest animate-pulse">Chargement...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {athletes.map(athlete => (
              <div key={athlete.id} className="bg-white rounded-[2.5rem] p-8 shadow-sm border border-brand-light space-y-6 hover:shadow-xl hover:shadow-brand-primary/10 transition-all group relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-brand-light/20 rounded-bl-[5rem] -mr-8 -mt-8 transition-transform group-hover:scale-110" />
                
                <div className="flex items-start justify-between relative z-10">
                  <div className="space-y-1">
                    <div className="text-[10px] font-black uppercase tracking-widest text-brand-primary">Athlète</div>
                    <div className="text-lg font-black text-brand-dark truncate w-48">{athlete.email}</div>
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => router.push(`/?athleteId=${athlete.id}`)}
                      className="p-3 bg-brand-surface text-brand-primary hover:text-white hover:bg-brand-primary rounded-xl transition-all shadow-sm"
                      title="Voir le calendrier"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="space-y-4 pt-4 border-t border-brand-surface relative z-10">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-brand-secondary font-bold uppercase text-[10px] tracking-widest">Objectif</span>
                    <span className="font-black text-brand-dark">{athlete.race_name}</span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-brand-surface p-4 rounded-2xl space-y-1 border border-brand-light/50">
                      <div className="text-[9px] font-black uppercase tracking-widest text-brand-secondary flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> Durée
                      </div>
                      <div className="text-sm font-black text-brand-dark">{athlete.duration_weeks} sem.</div>
                    </div>
                    <div className="bg-brand-surface p-4 rounded-2xl space-y-1 border border-brand-light/50">
                      <div className="text-[9px] font-black uppercase tracking-widest text-brand-accent flex items-center gap-1">
                        <TrendingUp className="w-3 h-3" /> Avancement
                      </div>
                      <div className="text-sm font-black text-brand-dark">{athlete.progress_weeks} sem.</div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-brand-secondary font-bold uppercase text-[10px] tracking-widest">Réalisation</span>
                      <span className="text-sm font-black text-brand-primary">{athlete.completion_rate.toFixed(1)}%</span>
                    </div>
                    <div className="w-full h-2 bg-brand-light rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-brand-primary transition-all shadow-sm" 
                        style={{ width: `${athlete.completion_rate}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

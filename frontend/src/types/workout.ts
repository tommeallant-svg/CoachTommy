export type WorkoutType = 'Endurance' | 'Tempo' | 'Seuil' | 'VO2 Max' | 'Sprint' | 'Libre' | 'Trail' | 'Fractionné' | 'Sortie Longue';

export interface WorkoutInterval {
  type: string;
  pace_min: string;
  pace_max: string;
  duration?: number;
  distance?: number;
}

export interface WorkoutBlock {
  repetitions: number;
  intervals: WorkoutInterval[];
}

export interface Workout {
  id: number;
  workout_type: string;
  category: string;
  name: string;
  duration_minutes: number;
  distance_km: number | null;
  difficulty_level: number;
  estimated_load: number | null;
  description: string;
  scheme: WorkoutBlock[] | null;
  date: string;
  is_validated: boolean;
  perceived_difficulty: number | null;
  athlete_comment: string | null;
  plan_id: number | null;
  athlete_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CatalogInterval {
  type: string;
  pace_vma_min: number; // en %
  pace_vma_max: number; // en %
  duration?: number;
  distance?: number;
}

export interface CatalogBlock {
  repetitions: number;
  intervals: CatalogInterval[];
}

export interface CatalogWorkout {
  id: number;
  name: string;
  workout_type: string;
  category: string;
  description?: string;
  perceived_difficulty: number;
  scheme: CatalogBlock[];
}

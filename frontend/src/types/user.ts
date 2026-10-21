export interface User {
  id: number;
  email: string;
  role: 'athlete' | 'coach';
  last_period_date?: string | null;
  cycle_length?: number;
  period_length?: number;
  vma?: number | null;
  ftp?: number | null;
}

export interface UserUpdateMenstrualCycle {
  last_period_date: string;
  cycle_length: number;
  period_length: number;
}

export interface UserUpdateStats {
  vma?: number;
  ftp?: number;
}

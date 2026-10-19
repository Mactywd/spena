// Le risposte di «Attività» (H2), come le scrive `backend/app/schemas/activity.py`. I giorni
// sono `YYYY-MM-DD` di Roma e le ore «18:05» di Roma: il fuso lo decide il server.

export type SyncStatus = "ok" | "test" | "rejected";

export interface ActivitySync {
  day: string;
  time: string;
  status: SyncStatus;
  /** più di 24 ore fa */
  stale: boolean;
  steps_days: number;
  exercises: number;
  weights: number;
  /** i nomi a video dei tipi arrivati e non usati */
  ignored: string[];
  problems: string[];
}

export interface StepsDay {
  day: string;
  /** `null`: nessun totale arrivato, che non vuol dire zero passi */
  steps: number | null;
}

export interface ExerciseSession {
  day: string;
  time: string;
  label: string;
  title: string | null;
  minutes: number;
  distance_km: number | null;
  /** il nome a video dell'app che l'ha scritto */
  source: string;
}

export interface WeighIn {
  day: string;
  time: string;
  kilograms: number;
}

export interface Connection {
  has_token: boolean;
  created_day: string | null;
  created_time: string | null;
  last_used_day: string | null;
  last_used_time: string | null;
}

export interface Activity {
  today: string;
  last_sync: ActivitySync | null;
  /** gli ultimi 7 giorni, oggi per primo */
  steps_days: StepsDay[];
  exercises: ExerciseSession[];
  weights: WeighIn[];
  connection: Connection;
}

/** La chiave appena creata: si vede solo qui, una volta. */
export interface NewToken {
  token: string;
  header: string;
}

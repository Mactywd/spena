import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { fetchActivity } from "./api";
import { dayLabel, exerciseLine, formatKg, formatSteps, ignoredText, syncText } from "./format";
import type { Activity } from "./types";

const ROW = "flex min-h-11 items-center justify-between gap-3 border-b border-line px-3 py-2 last:border-b-0";
const STACKED_ROW = "flex flex-col gap-0.5 border-b border-line px-3 py-2 last:border-b-0";

/** «Attività» (H2): cosa è arrivato da Health Connect via HC Webhook.
 *
 * Il server decide tutto — i giorni e le ore di Roma, i nomi, se la sincronizzazione è
 * vecchia —; qui si scrive e si disegna. Senza tasto indietro: ci si arriva dal ☰, come
 * all'Anagrafica. Niente grafici: sette numeri si leggono meglio in fila. */
export function ActivityScreen() {
  const activity = useQuery({ queryKey: ["activity"], queryFn: fetchActivity });

  return (
    <Screen title="Attività" subtitle="Passi, allenamenti e peso da Health Connect.">
      {activity.isPending ? (
        <p className="px-1 text-sm text-ink-soft">Carico l'attività…</p>
      ) : activity.isError ? (
        <ErrorState
          message="Non sono riuscito a leggere l'attività."
          onRetry={() => activity.refetch()}
          retrying={activity.isFetching}
        />
      ) : (
        <Report activity={activity.data} />
      )}
    </Screen>
  );
}

function Report({ activity }: { activity: Activity }) {
  const sync = activity.last_sync;
  // mai arrivato niente: cosa manca, e la strada (mai un vicolo cieco)
  if (sync === null) {
    return (
      <EmptyState
        title="Nessun dato da Health Connect, per ora"
        body="Spena riceve passi, allenamenti e pesate da HC Webhook, un'app per Android che li legge da Health Connect, dove li scrive Samsung Health. Si collega una volta sola."
        action={
          <Link to="/attivita/collega" className={buttonClasses("primary")}>
            Collega HC Webhook
          </Link>
        }
      />
    );
  }

  return (
    <div className="flex flex-col">
      <Card className="flex flex-col gap-2">
        <p className="text-sm">{syncText(sync, activity.today)}</p>
        {sync.stale && (
          <Alert tone="degraded">
            Da più di un giorno non arriva niente. Controlla che HC Webhook non sia limitato dall'ottimizzazione della
            batteria, e prova «Sincronizza ora».
          </Alert>
        )}
        {sync.problems.map((problem, index) => (
          <Alert key={index} tone="degraded">
            {problem}
          </Alert>
        ))}
        {sync.ignored.length > 0 && <p className="text-sm text-ink-soft">{ignoredText(sync.ignored)}</p>}
      </Card>

      <SectionHeading>Passi</SectionHeading>
      <Card pad={false}>
        <ul aria-label="Passi degli ultimi 7 giorni">
          {activity.steps_days.map((entry) => (
            <li key={entry.day} className={ROW}>
              <span className="text-sm">{dayLabel(entry.day, activity.today)}</span>
              {entry.steps === null ? (
                <span className="text-sm text-ink-soft">nessun dato</span>
              ) : (
                <span className="font-semibold tabular-nums">{formatSteps(entry.steps)}</span>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <SectionHeading>Allenamenti</SectionHeading>
      {activity.exercises.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-soft">Nessun allenamento negli ultimi 7 giorni.</p>
        </Card>
      ) : (
        <Card pad={false}>
          <ul aria-label="Allenamenti degli ultimi 7 giorni">
            {activity.exercises.map((exercise, index) => (
              <li key={`${exercise.day}-${exercise.time}-${index}`} className={STACKED_ROW}>
                <p className="text-sm font-medium">{exerciseLine(exercise)}</p>
                <p className="text-xs text-ink-soft">
                  {`${dayLabel(exercise.day, activity.today)}, ${exercise.time} · ${exercise.source}`}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <SectionHeading>Peso</SectionHeading>
      {activity.weights.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-soft">Nessuna pesata, per ora.</p>
        </Card>
      ) : (
        <Card pad={false}>
          <ul aria-label="Ultime pesate">
            {activity.weights.map((weight, index) => (
              <li key={`${weight.day}-${weight.time}-${index}`} className={ROW}>
                <span className="font-semibold tabular-nums">{formatKg(weight.kilograms)}</span>
                <span className="text-sm text-ink-soft">{`${dayLabel(weight.day, activity.today)}, ${weight.time}`}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="pt-4">
        <Link to="/attivita/collega" className={buttonClasses("secondary")}>
          Collegamento con HC Webhook
        </Link>
      </div>
    </div>
  );
}

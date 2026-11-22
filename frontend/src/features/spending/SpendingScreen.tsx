import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { fetchSpending } from "./api";
import { DailyColumns } from "./DailyColumns";
import { PlanSections } from "./PlanSections";
import { SectionBars } from "./SectionBars";
import { callsText, formatRange, formatUsd, unpricedText } from "./format";
import type { Spending, SpendingPeriod } from "./types";

// I tre periodi, decisi da Mattia il 2026-10-09, nell'ordine in cui si scelgono; il primo
// è quello di partenza. La frase è quella di un periodo senza chiamate.
const PERIODS: { value: SpendingPeriod; label: string; empty: string }[] = [
  { value: "month", label: "Questo mese", empty: "Nessuna chiamata all'AI questo mese." },
  { value: "30d", label: "Ultimi 30 giorni", empty: "Nessuna chiamata all'AI negli ultimi 30 giorni." },
  { value: "all", label: "Da sempre", empty: "Nessuna chiamata all'AI, finora." },
];

/** «Spese dell'AI» (H1): quanto è costata l'AI nel periodo, per sezione e giorno per
 * giorno, da `llm_calls`. Il server decide tutto — il periodo in giorni di Roma, le somme,
 * le quote, i nomi delle sezioni —; qui si sceglie il periodo e si disegna.
 *
 * Senza tasto indietro: ci si arriva dal ☰, come all'Anagrafica. Il periodo non si
 * ricorda: entrando si riparte da «Questo mese». Tre pulsanti a larghezza uguale con
 * `aria-pressed`, quello scelto `primary`: la forma di «Tutto / Cibo / Casa» (S14). */
export function SpendingScreen() {
  const [period, setPeriod] = useState<SpendingPeriod>("month");
  const spending = useQuery({
    queryKey: ["llm-spending", period],
    queryFn: () => fetchSpending(period),
  });
  const empty = PERIODS.find((entry) => entry.value === period)?.empty ?? PERIODS[0].empty;

  return (
    <Screen title="Spese dell'AI" subtitle="Quanto ha speso l'AI su OpenRouter, e per cosa.">
      <div role="group" aria-label="Periodo" className="flex gap-2">
        {PERIODS.map((entry) => (
          <Button
            key={entry.value}
            variant={entry.value === period ? "primary" : "secondary"}
            aria-pressed={entry.value === period}
            onClick={() => setPeriod(entry.value)}
            className="flex-1 text-center"
          >
            {entry.label}
          </Button>
        ))}
      </div>
      <div className="flex flex-col pt-4">
        {spending.isPending ? (
          <p className="px-1 text-sm text-ink-soft">Carico le spese…</p>
        ) : spending.isError ? (
          <ErrorState
            message="Non sono riuscito a leggere le spese."
            onRetry={() => spending.refetch()}
            retrying={spending.isFetching}
          />
        ) : (
          <Report spending={spending.data} empty={empty} />
        )}
      </div>
    </Screen>
  );
}

function Report({ spending, empty }: { spending: Spending; empty: string }) {
  const plan = spending.plan_sections ?? [];
  // un periodo senza chiamate è una frase, non un grafico vuoto (Mattia)
  if (spending.calls === 0) {
    return (
      <>
        <Card>
          <p className="text-sm text-ink-soft">{empty}</p>
        </Card>
        {plan.length > 0 && <PlanSections sections={plan} />}
      </>
    );
  }
  return (
    <>
      <Card>
        <p className="text-sm text-ink-soft">Totale, {formatRange(spending.first_day, spending.last_day)}</p>
        <p className="pt-1 text-4xl font-semibold tracking-tight">{formatUsd(spending.total_usd)}</p>
        <p className="pt-1 text-sm text-ink-soft">{callsText(spending.calls)}</p>
        {/* decisa da Mattia il 2026-10-13: senza questa riga il totale
            sembrerebbe completo anche quando non lo è */}
        {spending.unpriced_calls > 0 && (
          <p className="pt-1 text-sm text-ink-soft">{unpricedText(spending.unpriced_calls)}</p>
        )}
      </Card>
      {/* con chiamate ma nessun costo dichiarato, i due grafici sarebbero vuoti */}
      {spending.total_usd > 0 && (
        <>
          <SectionHeading>Per sezione</SectionHeading>
          <SectionBars sections={spending.sections} />
          <SectionHeading>Per giorno</SectionHeading>
          <DailyColumns days={spending.days} />
        </>
      )}
      {plan.length > 0 && <PlanSections sections={plan} />}
    </>
  );
}

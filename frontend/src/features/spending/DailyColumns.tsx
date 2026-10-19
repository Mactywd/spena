import { Card } from "../../components/ui/Card";
import { formatDay, formatDayShort, formatRange, formatUsd, peakDay } from "./format";
import type { DaySpend } from "./types";

// Una colonna ha accanto il suo spazio (un quinto della fetta: ~2 px su un mese a 375 px)
// finché i giorni sono al più due mesi; oltre, la fetta scende sotto i 5 px e lo spazio la
// cancellerebbe: le colonne si toccano e fanno una sagoma.
const GAPPED_UP_TO = 62;
const GAP = 0.2;
// Con pochi giorni (i primi del mese) una colonna non si allarga oltre quella che avrebbe
// con quattordici: un giorno solo largo tutta la scheda sembrerebbe un riquadro, non un dato.
const MIN_SLOTS = 14;
// Una spesa minuscola accanto a una grossa resterebbe sotto il pixel: due unità su cento la
// tengono visibile, senza farla sembrare grande.
const MIN_HEIGHT = 2;

/** «Per giorno» (H1): una colonna per ogni giorno con una spesa, alta in proporzione al
 * giorno più caro, sopra una linea di base; i giorni a zero non hanno colonna.
 *
 * Un `viewBox` di una unità per giorno e cento in altezza, stirato sulla larghezza della
 * scheda (`preserveAspectRatio="none"`): niente misure in pixel da calcolare, niente
 * scorrimento di lato, nemmeno con un anno di giorni. Per questo niente angoli arrotondati
 * (si deformerebbero) e la linea di base non scala (`non-scaling-stroke`). Niente testo
 * dentro l'SVG: il giorno più caro e le date stanno in HTML, dove li misura lo scanner del
 * contrasto.
 *
 * Le colonne non si toccano una per una: trenta colonne su 375 px sono larghe 10 px, sotto
 * i 44 di casa. Chi non vede ha il riassunto nel nome dell'immagine e la tabella dei giorni
 * con una spesa. Senza nessun giorno con una spesa non disegna niente: un grafico vuoto
 * non dice niente che il totale non dica già. */
export function DailyColumns({ days }: { days: DaySpend[] }) {
  const peak = peakDay(days);
  if (peak === null) return null;

  const count = days.length;
  const first = days[0].day;
  const last = days[count - 1].day;
  const width = count < MIN_SLOTS ? ((1 - GAP) * count) / MIN_SLOTS : count <= GAPPED_UP_TO ? 1 - GAP : 1;
  const height = (cost: number) => Math.max((cost / peak.cost_usd) * 100, MIN_HEIGHT);
  const peakText = `Il giorno più caro: ${formatDay(peak.day)}, ${formatUsd(peak.cost_usd)}`;

  return (
    <Card>
      <p className="text-sm text-ink-soft">{peakText}</p>
      <svg
        role="img"
        aria-label={`Costo per giorno, ${formatRange(first, last)}. ${peakText}.`}
        viewBox={`0 0 ${count} 102`}
        preserveAspectRatio="none"
        className="mt-2 block h-32 w-full"
      >
        {days.map((day, index) =>
          day.cost_usd > 0 ? (
            <rect
              key={day.day}
              data-day={day.day}
              x={index + (1 - width) / 2}
              width={width}
              y={100 - height(day.cost_usd)}
              height={height(day.cost_usd)}
              className="fill-brand"
            />
          ) : null
        )}
        <line
          x1="0"
          x2={count}
          y1="101"
          y2="101"
          strokeWidth="1"
          vectorEffect="non-scaling-stroke"
          className="stroke-line"
        />
      </svg>
      <div className={`flex pt-1 text-xs text-ink-faint ${first === last ? "justify-center" : "justify-between"}`}>
        <span>{formatDayShort(first)}</span>
        {first !== last && <span>{formatDayShort(last)}</span>}
      </div>
      <table className="sr-only">
        <caption>I giorni con una spesa</caption>
        <tbody>
          {days
            .filter((day) => day.cost_usd > 0)
            .map((day) => (
              <tr key={day.day}>
                <th scope="row">{formatDay(day.day)}</th>
                <td>{formatUsd(day.cost_usd)}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </Card>
  );
}

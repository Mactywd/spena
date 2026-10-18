import { formatNutrient, type NutrientRow } from "../lib/nutrients";

/** I nutrienti in una tabella da leggere (S4). Le otto righe dell'etichetta sempre, con
 * «—» dove la fonte non dà il valore — mai uno zero, che sarebbe un'affermazione; gli
 * altri, se ce ne sono, sotto «Vitamine e minerali», chiusi: su un telefono ventidue righe
 * di micronutrienti spingerebbero fuori tutto il resto. Quali sono i principali lo dice
 * il server (`main`). */
export function NutrientTable({ caption, rows }: { caption: string; rows: NutrientRow[] }) {
  const main = rows.filter((row) => row.main);
  const extra = rows.filter((row) => !row.main && row.value !== null);
  return (
    <div>
      <table className="w-full text-sm">
        <caption className="pb-1 text-left text-xs text-ink-soft">{caption}</caption>
        <tbody>
          {main.map((row) => (
            <NutrientTableRow key={row.key} row={row} />
          ))}
        </tbody>
      </table>
      {extra.length > 0 && (
        <details className="mt-1">
          {/* il sommario è il bersaglio: 44 px, come ogni altro */}
          <summary className="flex min-h-11 cursor-pointer items-center text-sm font-medium text-brand">
            Vitamine e minerali ({extra.length})
          </summary>
          <table className="w-full text-sm">
            <tbody>
              {extra.map((row) => (
                <NutrientTableRow key={row.key} row={row} />
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}

function NutrientTableRow({ row }: { row: NutrientRow }) {
  return (
    <tr>
      <th scope="row" className="py-1 pr-2 text-left font-normal text-ink-soft">
        {row.label}
      </th>
      <td className="py-1 text-right tabular-nums">
        {row.value === null ? (
          <>
            <span aria-hidden="true">—</span>
            <span className="sr-only">non indicato nella tabella</span>
          </>
        ) : (
          formatNutrient(row.value, row.unit)
        )}
        {row.note && <span className="block text-xs text-ink-faint">{row.note}</span>}
      </td>
    </tr>
  );
}

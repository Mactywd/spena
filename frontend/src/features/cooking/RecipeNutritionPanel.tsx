import { useId, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { NutrientTable } from "../../components/NutrientTable";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { capitalizeFirst } from "../../lib/text";
import type { NutrientRow } from "../../lib/nutrients";
import {
  captionText,
  countedText,
  fetchRecipeNutrition,
  missingText,
  partialNote,
  recipeNutritionKey,
  type RecipeNutrition,
} from "./recipeNutrition";

/** «Valori nutrizionali» in fondo al dettaglio della ricetta (spec S4 §4.28).
 *
 * Chiuso finché non lo si apre: è una stima, e non deve competere con «Cucina». Legge solo
 * quando si apre (decisione 15 del piano). Le righe fuori dal conto dicono perché, e il
 * nome porta alla scheda in Anagrafica, dove si sceglie l'alimento o si scrive il peso:
 * mai un vicolo cieco. */
export function RecipeNutritionPanel({ recipeId }: { recipeId: string }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const query = useQuery({
    queryKey: recipeNutritionKey(recipeId),
    queryFn: () => fetchRecipeNutrition(recipeId),
    enabled: open,
  });

  let body: ReactNode = null;
  if (open) {
    if (query.isLoading) {
      body = <p className="text-sm text-ink-soft">Calcolo i valori nutrizionali…</p>;
    } else if (query.isError || !query.data) {
      body = (
        <div className="flex flex-col items-start gap-2">
          <p className="text-sm text-ink-soft">Non sono riuscito a calcolare i valori nutrizionali.</p>
          <Button variant="secondary" onClick={() => void query.refetch()}>
            Riprova a calcolarli
          </Button>
        </div>
      );
    } else {
      body = <Breakdown data={query.data} />;
    }
  }

  return (
    <section>
      <SectionHeading>Valori nutrizionali</SectionHeading>
      <Card className="flex flex-col gap-3">
        <div className="flex flex-col items-start">
          <Button variant="secondary" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
            {open ? "Nascondi i valori nutrizionali" : "Mostra i valori nutrizionali"}
          </Button>
        </div>
        {open && (
          <div id={panelId} className="flex flex-col gap-3">
            {body}
          </div>
        )}
      </Card>
    </section>
  );
}

function Breakdown({ data }: { data: RecipeNutrition }) {
  const rows: NutrientRow[] = data.nutrients.map((nutrient) => ({
    key: nutrient.key,
    label: nutrient.label,
    unit: nutrient.unit,
    main: nutrient.main,
    value: nutrient.value,
    note: partialNote(nutrient, data.lines_counted),
  }));
  return (
    <>
      {data.lines_counted === 0 ? (
        <p className="text-sm">
          Nessuna riga si può contare ancora: servono gli alimenti CIQUAL degli ingredienti e i pesi delle
          loro dosi, in Anagrafica.
        </p>
      ) : (
        <NutrientTable caption={captionText(data)} rows={rows} />
      )}
      <p className="text-sm">{countedText(data.lines_counted, data.lines_total)}</p>
      {data.missing.length > 0 && (
        <div className="text-sm">
          <p className="text-ink-soft">Fuori dal conto:</p>
          <ul>
            {data.missing.map((line) => (
              <li key={line.ingredient_id}>
                {/* il nome apre la riga: la maiuscola solo a video (spec T3 §4.7) */}
                <Link
                  to={`/anagrafica/ingrediente/${line.ingredient_id}`}
                  className="inline-flex min-h-11 items-center font-medium text-brand"
                >
                  {capitalizeFirst(line.ingredient_name)}
                </Link>
                <span>
                  {line.quantity_text ? ` (${line.quantity_text})` : ""}: {missingText(line)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <p className="text-xs text-ink-faint">
        Stima con i valori medi di CIQUAL 2025 e i pesi delle dosi: non è un'etichetta.
      </p>
    </>
  );
}

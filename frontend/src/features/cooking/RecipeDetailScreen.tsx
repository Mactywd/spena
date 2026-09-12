import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { fetchRecipe } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { CookSheet } from "./CookSheet";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { CookResult, RecipeIngredientLine } from "../../domain/types";

function statusNote(line: RecipeIngredientLine): string {
  if (line.availability === "missing") return "manca";
  if (line.availability === "available") return "disponibile";
  // l'unico caso interessante: quasi finito, dove il ruolo fa la differenza
  return line.satisfied ? "quasi finito, basta" : "quasi finito, non basta";
}

// Il numero viene dal backend, non da un conteggio fatto qui: quante voci sono
// tornate in lista lo sa solo chi ha applicato le transizioni (una lista può già
// contenere quell'ingrediente, e allora non si duplica).
function cookNote(result: CookResult): string {
  if (result.restocked === 0) return "Segnato. Niente è tornato in lista della spesa.";
  if (result.restocked === 1) return "Segnato. Una cosa è tornata in lista della spesa.";
  return `Segnato. ${result.restocked} cose sono tornate in lista della spesa.`;
}

export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  const [cooking, setCooking] = useState(false);
  // l'esito dell'ultima cottura: il foglio si smonta subito dopo averla registrata,
  // e senza questo il gesto per cui esiste tutto il task non dice mai cosa ha fatto
  const [lastCook, setLastCook] = useState<CookResult | null>(null);

  const {
    data: recipe,
    isLoading: isRecipeLoading,
    isError: isRecipeError,
    refetch: refetchRecipe,
  } = useQuery({
    queryKey: ["recipe", id],
    queryFn: () => fetchRecipe(id),
  });

  // Serve solo per aprire il foglio di cottura: senza dispensa non si può dire
  // quali vasetti esistono, quindi un fallimento qui non può travestirsi da
  // "nessun vasetto da aggiornare" — altrimenti "Cucina" apparirebbe disponibile
  // ma produrrebbe un foglio vuoto, silenziosamente sbagliato.
  const {
    data: pantry,
    isLoading: isPantryLoading,
    isError: isPantryError,
    refetch: refetchPantry,
  } = useQuery({ queryKey: ["pantry"], queryFn: fetchPantry });

  if (isRecipeLoading) return <p className="p-4 text-ink-soft">Carico…</p>;

  // un caricamento fallito non è una ricetta vuota: dirlo sarebbe una bugia su
  // cosa serve e cosa si ha
  if (isRecipeError || !recipe) {
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <Alert>Non sono riuscito a caricare questa ricetta. Riprova.</Alert>
        <button
          type="button"
          onClick={() => void refetchRecipe()}
          className={buttonClasses("secondary")}
        >
          Riprova
        </button>
      </div>
    );
  }

  const primary = recipe.ingredients.filter((line) => line.role === "primary");
  const secondary = recipe.ingredients.filter((line) => line.role === "secondary");
  const groups: { label: string; lines: RecipeIngredientLine[] }[] = [
    { label: "Principali", lines: primary },
    { label: "Secondari", lines: secondary },
  ];

  return (
    <div className="px-4 pt-5 pb-4">
      <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
      {recipe.description && <p className="pt-1 text-ink-soft">{recipe.description}</p>}

      {/* L'attribuzione a un tocco. Solo se la provenienza è davvero un indirizzo:
          per le ricette del seme `source_ref` è una nota («seme iniziale»), e un
          collegamento a quella sarebbe un collegamento rotto.
          `rel="noreferrer"` perché il sito di origine non ha bisogno di sapere da
          dove arriva la visita. */}
      {recipe.source_ref?.startsWith("http") && (
        <a
          href={recipe.source_ref}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-brand"
        >
          Apri l'originale
        </a>
      )}

      {cooking && pantry ? (
        <div className="pt-4">
          <CookSheet
            recipe={recipe}
            pantryItems={pantry}
            onDone={(result) => {
              if (result) setLastCook(result);
              setCooking(false);
            }}
          />
        </div>
      ) : (
        <>
          {lastCook && (
            <p
              role="status"
              className="mt-3 rounded-card bg-brand-tint px-3 py-2.5 text-sm text-brand"
            >
              {cookNote(lastCook)}
            </p>
          )}

          {groups.map(({ label, lines }) => (
            <section key={label}>
              <SectionHeading>{label}</SectionHeading>
              <Card pad={false}>
                <ul className="divide-y divide-line">
                  {lines.map((line) => (
                    <li
                      key={line.ingredient_id}
                      className="flex items-baseline justify-between gap-2 px-3 py-2.5"
                    >
                      <span>
                        {line.ingredient_name}
                        {line.quantity_text && (
                          <span className="ml-2 text-sm text-ink-faint">{line.quantity_text}</span>
                        )}
                      </span>
                      {/* gli stessi due colori della dispensa: il verdetto per riga è
                          la stessa regola primario/secondario vista ingrediente per
                          ingrediente */}
                      <span
                        className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                          line.satisfied ? "bg-brand-tint text-brand" : "bg-low-tint text-low"
                        }`}
                      >
                        {statusNote(line)}
                      </span>
                    </li>
                  ))}
                </ul>
              </Card>
            </section>
          ))}

          <section>
            <SectionHeading>Procedimento</SectionHeading>
            {/* leggere mentre si cucina: interlinea larga, perché si torna a cercare
                il punto in cui si era con le mani sporche e lo sguardo di sbieco */}
            <Card>
              <p className="leading-relaxed whitespace-pre-line">{recipe.instructions}</p>
            </Card>
          </section>

          {/* "Cucina" apre il foglio di cottura, che ha bisogno della dispensa per
              elencare i vasetti concreti: senza quella, il pulsante dice perché non
              si può procedere invece di aprire un foglio vuoto e muto */}
          {isPantryError ? (
            <div className="mt-6 flex flex-col items-start gap-3">
              <Alert>
                Non sono riuscito a caricare la dispensa: non posso avviare la cottura.
              </Alert>
              <button
                type="button"
                onClick={() => void refetchPantry()}
                className={buttonClasses("secondary")}
              >
                Riprova
              </button>
            </div>
          ) : (
            <>
              <button
                type="button"
                // un esito vecchio non deve sopravvivere alla cottura successiva
                onClick={() => {
                  setLastCook(null);
                  setCooking(true);
                }}
                disabled={isPantryLoading}
                className={`${buttonClasses("primary", "block")} mt-6`}
              >
                Cucina
              </button>
              {/* un pulsante grigio e muto non si spiega da sé: dire che manca la
                  dispensa costa una riga e toglie l'unico dubbio */}
              {isPantryLoading && (
                <p className="pt-2 text-xs text-ink-soft">Carico la dispensa…</p>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

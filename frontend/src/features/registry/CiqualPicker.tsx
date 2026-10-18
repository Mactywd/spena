import { useDeferredValue, useId, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { registryRefusal } from "./api";
import { chooseFood, nutritionKey, searchCiqual } from "./nutrition";

/** La correzione dell'alimento CIQUAL (spec S4 §4.14). Si cerca in francese, come scrive
 * la tabella, o per codice; i risultati sono radio veri — selezione singola e frecce
 * della tastiera — col nome come nome accessibile e il gruppo come descrizione. «Nessun
 * alimento adatto» è una scelta anche lei, e si salva. Un rifiuto lascia la ricerca
 * aperta, per scegliere un altro alimento. */
export function CiqualPicker({
  ingredientId,
  current,
  onDone,
}: {
  ingredientId: string;
  /** il codice che l'ingrediente ha già, se ne ha uno */
  current: string | null;
  /** `true` se ha salvato */
  onDone: (saved: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState("");
  // la ricerca segue il campo senza rincorrere ogni lettera
  const term = useDeferredValue(query.trim());
  const [chosen, setChosen] = useState<string | null>(null);
  const fieldId = useId();
  const hintId = useId();
  const radioName = useId();

  const search = useQuery({
    queryKey: ["ciqual-foods", term],
    queryFn: () => searchCiqual(term),
    enabled: term.length >= 2,
  });
  const save = useMutation({
    mutationFn: (code: string | null) => chooseFood(ingredientId, code),
    onSuccess: (next) => {
      queryClient.setQueryData(nutritionKey(ingredientId), next);
      onDone(true);
    },
  });
  const refusal = registryRefusal(save.error);
  const results = term.length >= 2 ? search.data : undefined;
  const reason =
    chosen === null
      ? "Scegli un alimento dall'elenco."
      : chosen === current
        ? "È già il suo alimento: scegline un altro."
        : undefined;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor={fieldId} className="text-sm font-medium">
          Cerca nella tabella CIQUAL
        </label>
        <input
          id={fieldId}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          autoComplete="off"
          enterKeyHint="search"
          aria-describedby={hintId}
        />
        <p id={hintId} className="text-xs text-ink-soft">
          Scrivi in francese, come la tabella: «tomate», «farine», «beurre».
        </p>
      </div>
      {term.length >= 2 && search.isError && <Alert>Non sono riuscito a cercare. Riprova fra poco.</Alert>}
      {results !== undefined && results.length === 0 && (
        <p className="text-sm text-ink-soft">Nessun alimento trovato: prova un'altra parola, in francese.</p>
      )}
      {results !== undefined && results.length > 0 && (
        // scorre nel suo riquadro, come i suggerimenti della lista: quindici risultati
        // sotto la tastiera aperta non devono far scorrere la pagina
        <div
          role="radiogroup"
          aria-label="Alimenti trovati"
          className="flex max-h-[min(18rem,45dvh)] flex-col overflow-y-auto overscroll-contain"
        >
          {results.map((food) => {
            const groupId = `${radioName}-${food.code}`;
            return (
              <label key={food.code} className="flex min-h-11 items-center gap-3 py-1.5 text-sm">
                <input
                  type="radio"
                  name={radioName}
                  value={food.code}
                  checked={chosen === food.code}
                  onChange={() => setChosen(food.code)}
                  aria-label={food.name_fr}
                  aria-describedby={food.group_fr ? groupId : undefined}
                  className="size-5 shrink-0 accent-brand"
                />
                <span className="min-w-0 flex-1">
                  <span className="block">{food.name_fr}</span>
                  {food.group_fr && (
                    <span id={groupId} className="block text-xs text-ink-soft">
                      {food.group_fr}
                    </span>
                  )}
                </span>
              </label>
            );
          })}
        </div>
      )}
      {/* in colonna: il perché di «Salva l'alimento» sta attaccato sotto di lui */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending && save.variables !== null}
          unavailableReason={reason}
          onClick={() => {
            if (chosen !== null) save.mutate(chosen);
          }}
        >
          Salva l'alimento
        </Button>
        <Button
          variant="secondary"
          busy={save.isPending && save.variables === null}
          onClick={() => save.mutate(null)}
        >
          Nessun alimento adatto
        </Button>
        <Button variant="ghost" onClick={() => onDone(false)}>
          Lascia com'è
        </Button>
      </div>
      {refusal !== null && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && <Alert>Non sono riuscito a salvare la scelta. Riprova.</Alert>}
    </div>
  );
}

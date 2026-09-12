import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "./api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { OptionList } from "../../components/ui/OptionList";
import { buttonClasses } from "../../components/ui/buttonClasses";

const DEBOUNCE_MS = 180;

export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => Promise<unknown> | void;
}) {
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);
  const term = useDebounced(text, DEBOUNCE_MS).trim();
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const enabled = term.length >= 2;

  // La ricerca passa da `useQuery`, come in RecipeBookScreen e in IngredientPicker.
  // Due cose che un `.catch` locale non dà. La sicurezza sull'ordine diventa
  // strutturale: il termine sta nella chiave, quindi una risposta superata atterra
  // sotto la propria chiave e non può sovrascrivere suggerimenti più recenti. E un
  // 401 arriva alla QueryCache che App.tsx aggancia al ritorno all'accesso: prima
  // moriva qui dentro, e a sessione scaduta il campo smetteva di suggerire senza
  // dire perché — gli altri due consumatori della stessa ricerca erano già stati
  // corretti, questo era il terzo.
  const { data: suggestions = [], isError } = useQuery({
    queryKey: ["ingredients", term],
    queryFn: () => searchIngredients(term),
    enabled,
  });

  // sul testo corrente, non sul termine ritardato: svuotando il campo i
  // suggerimenti devono sparire subito, non dopo l'attesa
  const showSuggestions = text.trim().length >= 2;

  async function add(rawText: string, ingredientId?: string) {
    setFailed(false);
    try {
      await onAdd(rawText, ingredientId);
    } catch {
      // il testo resta nel campo. Svuotarlo prima di sapere com'è andata perde
      // quello che l'utente ha scritto, che è il peggiore dei vicoli ciechi
      setFailed(true);
      return;
    }
    setText("");
  }

  function submitFreeText(event: FormEvent) {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    // niente corrispondenza non è un errore: la voce entra grezza
    void add(trimmed, undefined);
  }

  return (
    // appiccicato in alto, col fondo della pagina dietro: scorrendo i reparti il
    // campo per scrivere non deve andarsene. Il titolo invece scorre via — è
    // orientamento, e serve una volta
    <form onSubmit={submitFreeText} className="sticky top-0 z-10 bg-page px-4 pt-1 pb-3">
      <label htmlFor="add-item" className="sr-only">Aggiungi alla lista</label>
      <div className="flex gap-2">
        <input
          id="add-item"
          aria-label="Aggiungi alla lista"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Cosa serve?"
          className="min-w-0 flex-1"
        />
        {/* un bersaglio visibile: da telefono il tasto invio della tastiera non si
            vede, e il testo libero è il percorso che non deve mai essere nascosto */}
        <button
          type="submit"
          disabled={text.trim().length === 0}
          className={`${buttonClasses("primary")} shrink-0`}
        >
          Aggiungi
        </button>
      </div>
      {failed && (
        <Alert className="pt-2">
          Non sono riuscito ad aggiungere la voce. Il testo è ancora qui: riprova.
        </Alert>
      )}
      {/* una ricerca che non risponde non deve bloccare la scrittura, e nemmeno
          restare muta: il testo libero passa comunque, e va detto che passerà
          senza ingrediente abbinato. `status` e non `alert`: è una rinuncia, non
          un guasto da interrompere quel che si sta scrivendo.
          Il colore è quello di «quasi finito», e di proposito: nell'app l'ambra
          vuol dire sempre «funziona, ma non del tutto». */}
      {showSuggestions && isError && (
        <p role="status" className="pt-2 text-sm text-low">
          L'autocomplete non risponde. Puoi aggiungere la voce così com'è: l'ingrediente
          si abbina dopo.
        </p>
      )}
      {showSuggestions && suggestions.length > 0 && (
        <div className="pt-2">
          <OptionList
            options={suggestions}
            onPick={(ingredient) => void add(ingredient.name, ingredient.id)}
          />
        </div>
      )}
    </form>
  );
}

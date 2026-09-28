import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "./api";
import { useDebounced } from "../../hooks/useDebounced";
import { ActionBar } from "../../components/ui/ActionBar";
import { Alert } from "../../components/ui/Alert";
import { OptionList } from "../../components/ui/OptionList";
import { useNotice } from "../../components/ui/noticeContext";
import type { RestockResult } from "../../domain/types";

const DEBOUNCE_MS = 180;

/** La barra in cima alla Lista (spec T3 §4.2): «Cosa manca?» e il +, con i suggerimenti
 * dell'anagrafica sotto. Il testo libero passa sempre, con l'Invio o col +: se coincide
 * con un ingrediente lo aggancia il backend (S18). */
export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => Promise<RestockResult>;
}) {
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);
  const notice = useNotice();
  const term = useDebounced(text, DEBOUNCE_MS).trim();
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const enabled = term.length >= 2;

  // La ricerca passa da `useQuery`, come in IngredientPicker: il termine sta nella
  // chiave, quindi una risposta superata atterra sotto la propria chiave e non può
  // sovrascrivere suggerimenti più recenti; e un 401 arriva alla QueryCache che
  // App.tsx aggancia al ritorno all'accesso, invece di morire qui dentro.
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
    let result: RestockResult;
    try {
      result = await onAdd(rawText, ingredientId);
    } catch {
      // il testo resta nel campo. Svuotarlo prima di sapere com'è andata perde
      // quello che l'utente ha scritto, che è il peggiore dei vicoli ciechi
      setFailed(true);
      return;
    }
    // svuotato anche quando c'era già: quel che si voleva in lista ci sta
    setText("");
    // S18: l'ingrediente era già da comprare e il backend non ha scritto il doppione.
    // Un'informazione, non un errore: l'avviso unico, con le parole della dispensa
    if (!result.added) notice({ text: "Era già in lista." });
  }

  return (
    // Appiccicata appena sotto l'intestazione (`top-12` è l'altezza di AppHeader), non
    // sopra: con `top-0` e lo stesso `z-10` dell'intestazione la copriva scorrendo (dal
    // giro). `-mx-4 px-4` porta il fondo da bordo a bordo, o nei margini di `Screen` le
    // righe si vedrebbero scorrere ai lati della barra.
    <div className="sticky top-12 z-5 -mx-4 bg-page px-4 pt-1 pb-3">
      <ActionBar
        inputLabel="Aggiungi alla lista"
        placeholder="Cosa manca?"
        addLabel="Aggiungi"
        value={text}
        onChange={(value) => {
          setText(value);
          setFailed(false);
        }}
        onAdd={(value) => void add(value, undefined)}
      />
      {failed && (
        <Alert className="pt-2">
          Non sono riuscito ad aggiungere la voce. Il testo è ancora qui: riprova.
        </Alert>
      )}
      {/* una ricerca che non risponde non deve bloccare la scrittura, e nemmeno restare
          muta: il testo libero passa comunque, e va detto che passerà senza ingrediente
          abbinato. `status` e non `alert`: è una rinuncia, non un guasto. L'ambra di
          «quasi finito» vuol dire, nell'app, «funziona, ma non del tutto». */}
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
            fieldLabel="Aggiungi alla lista"
            onPick={(ingredient) => void add(ingredient.name, ingredient.id)}
          />
        </div>
      )}
    </div>
  );
}

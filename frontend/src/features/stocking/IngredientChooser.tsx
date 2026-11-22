import { useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { NewIngredientFields } from "./NewIngredientFields";
import { createIngredient } from "../shopping-list/api";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import type { Ingredient } from "../../domain/types";

/** L'ingrediente omonimo che il 409 di `POST /ingredients` porta in `existing`, se
 * l'errore è quello. Ogni altro fallimento torna `null` e tiene il suo messaggio. */
function existingIngredient(error: unknown): Ingredient | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (body === null || typeof body !== "object" || !("existing" in body)) return null;
  return (body as { existing: Ingredient }).existing ?? null;
}

/**
 * Scegliere un ingrediente dal selettore unico (spec §3.5), oppure crearlo. Estratto da
 * `MatchPanel` (S3): lo usano «Abbina» e «Articolo aggiuntivo» in «Sistema la spesa», il
 * + della Dispensa e il passo «Di che ingrediente è?» della sua scansione. Il sistema non
 * inventa niente da solo.
 *
 * La creazione è sempre raggiungibile, anche quando la ricerca trova qualcosa
 * (`createWhen="always"`): legarla all'assenza di suggerimenti era il difetto S6,
 * corretto il 2026-09-20 — misurato in produzione, di sette nomi plausibili di prodotti
 * per la casa tutti e sette pescavano almeno un suggerimento.
 *
 * «Abbina» chiede l'elenco intero, senza il taglio dei suggerimenti: vedi `IngredientPicker`.
 *
 * Un frammento: `before` e `after` (una frase, un «Annulla») stanno nella colonna di chi
 * lo usa, e solo mentre si sceglie — mentre si crea, `NewIngredientFields` ha il suo
 * «Annulla», che torna alla scelta.
 */
export function IngredientChooser({
  label,
  accessibleLabel,
  failureNote,
  initialTerm,
  onChosen,
  busy = false,
  before,
  after,
  trim = true,
}: {
  label: string;
  accessibleLabel?: string;
  failureNote: string;
  initialTerm: string;
  onChosen: (ingredient: Ingredient) => void;
  /** La scrittura nata dalla scelta precedente è ancora in volo. */
  busy?: boolean;
  before?: ReactNode;
  after?: ReactNode;
  /** Passata a `IngredientPicker`: `false` chiede l'elenco intero. */
  trim?: boolean;
}) {
  // `null`: si cerca. Una stringa: si crea, e il campo del nome parte da lì
  const [creating, setCreating] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async ({ name, category }: { name: string; category: string }) => {
      try {
        // name e display_name sono lo stesso testo: il backend normalizza il primo
        // (strip + lower), e inventare noi una forma canonica sarebbe logica di dominio
        // sul client
        return await createIngredient({ name, display_name: name, category });
      } catch (error) {
        // Il nome c'è già (S19): il 409 porta l'ingrediente che ce l'ha, e quello si
        // sceglie. Chi è «lo stesso nome» lo decide il backend, che lo ha appena
        // rifiutato: niente confronto di nomi qui.
        const existing = existingIngredient(error);
        if (existing) return existing;
        throw error;
      }
    },
  });

  if (creating === null) {
    return (
      <>
        {before}
        <IngredientPicker
          label={label}
          accessibleLabel={accessibleLabel}
          failureNote={failureNote}
          initialTerm={initialTerm}
          autoFocus
          onPick={onChosen}
          onCreate={(name) => setCreating(name)}
          createWhen="always"
          disabled={busy}
          trim={trim}
        />
        {after}
      </>
    );
  }

  return (
    <>
      <NewIngredientFields
        initialName={creating}
        busy={create.isPending}
        // `onSuccess` passato a `mutate` e non alle opzioni di `useMutation`: queste
        // girano dalla Mutation stessa anche dopo `reset()`, e «Annulla» durante la
        // creazione in volo sceglierebbe l'ingrediente scartato; quelle di `mutate` si
        // fermano quando `reset()` stacca l'osservatore. Solo l'ingrediente: chi usa la
        // scelta si aspetta un unico argomento
        onSubmit={(fields) =>
          create.mutate(fields, { onSuccess: (ingredient) => onChosen(ingredient) })
        }
        onCancel={() => {
          create.reset();
          setCreating(null);
        }}
      />
      {create.isError && (
        <Alert>
          Non sono riuscito a creare l'ingrediente. Quel che hai scritto è ancora qui:
          riprova, oppure torna indietro e scegline uno.
        </Alert>
      )}
    </>
  );
}

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { NewIngredientFields } from "./NewIngredientFields";
import { createIngredient } from "../shopping-list/api";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/** L'ingrediente omonimo che il 409 di `POST /ingredients` porta in `existing`, se
 * l'errore è quello. Ogni altro fallimento torna `null` e tiene il suo messaggio. */
function existingIngredient(error: unknown): Ingredient | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (body === null || typeof body !== "object" || !("existing" in body)) return null;
  return (body as { existing: Ingredient }).existing ?? null;
}

/**
 * «Abbina», sotto una voce spuntata senza ingrediente (spec T3 §4.3): il testo libero
 * della lista non ha mai trovato un corrispondente, e la voce non può sparire in
 * silenzio dal conto finale. Qui il sistema non inventa niente da solo: si sceglie un
 * ingrediente dal selettore unico (spec §3.5), oppure lo si crea.
 *
 * La creazione è sempre raggiungibile, anche quando la ricerca trova qualcosa
 * (`createWhen="always"`): legarla all'assenza di suggerimenti era il difetto S6,
 * corretto il 2026-09-20 — misurato in produzione, di sette nomi plausibili di prodotti
 * per la casa tutti e sette pescavano almeno un suggerimento. Questo resta l'unico posto
 * dell'app che crea un ingrediente da una voce di lista.
 */
export function MatchPanel({
  item,
  onMatched,
  onCancel,
}: {
  item: ShoppingItem;
  onMatched: (ingredient: Ingredient) => void;
  onCancel: () => void;
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
        // aggancia. Chi è «lo stesso nome» lo decide il backend, che lo ha appena
        // rifiutato: niente confronto di nomi qui.
        const existing = existingIngredient(error);
        if (existing) return existing;
        throw error;
      }
    },
    // solo l'ingrediente: `useMutation` passerebbe a `onSuccess` anche `variables` e
    // `context`, e chi riceve `onMatched` (qui i test, e il Task 7) si aspetta un
    // unico argomento
    onSuccess: (ingredient) => onMatched(ingredient),
  });

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h3 className="font-semibold">Abbina «{item.raw_text}»</h3>
      {creating === null ? (
        <>
          <p className="text-sm text-ink-soft">
            Scegli a quale ingrediente corrisponde: senza, non entra in dispensa.
          </p>
          <IngredientPicker
            label="Abbina un ingrediente"
            accessibleLabel={`Abbina un ingrediente per ${item.raw_text}`}
            failureNote="Puoi comunque aggiungerlo."
            initialTerm={item.raw_text}
            autoFocus
            onPick={onMatched}
            onCreate={(name) => setCreating(name)}
            createWhen="always"
          />
          <Button variant="ghost" onClick={onCancel} className="self-start">
            Annulla
          </Button>
        </>
      ) : (
        <>
          <NewIngredientFields
            initialName={creating}
            busy={create.isPending}
            onSubmit={(fields) => create.mutate(fields)}
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
      )}
    </div>
  );
}

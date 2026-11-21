import { useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { UtensilRow } from "./UtensilRow";
import { UTENSILS_KEY, createUtensil, fetchUtensils } from "./api";

/** «Utensili», dal ☰ (spec 2026-11-12 §4.4 e §5.4): gli strumenti che Mattia ha in
 * cucina. Le ricette che l'AI scrive usano solo questi, e senza utensili scrive come
 * prima. L'elenco non ha legami con ingredienti o dispensa.
 *
 * «Togli» non chiede conferma (decisione 10): l'avviso che segue ha «Annulla», che
 * riscrive l'utensile com'era. Una conferma in più su un gesto che si disfa non serve.
 * Pulizia del testo e ordine dell'elenco sono del server: qui si manda quel che si scrive. */
export function UtensilsScreen() {
  const queryClient = useQueryClient();
  const nameRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const list = useQuery({ queryKey: UTENSILS_KEY, queryFn: fetchUtensils });

  const add = useMutation({
    mutationFn: () => createUtensil({ name, note: note === "" ? null : note }),
    onSuccess: async () => {
      setName("");
      setNote("");
      nameRef.current?.focus();
      await queryClient.invalidateQueries({ queryKey: UTENSILS_KEY });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === "" || add.isPending) return;
    add.mutate();
  }

  return (
    <Screen title="Utensili" subtitle="Gli strumenti che hai in cucina.">
      <form onSubmit={submit} className="flex flex-col items-start gap-3">
        <label className="block w-full text-sm font-medium text-ink-soft">
          Nuovo utensile
          <input
            ref={nameRef}
            value={name}
            onChange={(event) => setName(event.target.value)}
            maxLength={120}
            placeholder="padella antiaderente"
            className="mt-1.5"
          />
        </label>
        <label className="block w-full text-sm font-medium text-ink-soft">
          Nota del nuovo utensile
          <input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={200}
            placeholder="da 24 cm (facoltativa)"
            className="mt-1.5"
          />
        </label>
        <Button
          type="submit"
          variant="primary"
          busy={add.isPending}
          unavailableReason={name.trim() === "" ? "Scrivi il nome dell'utensile." : undefined}
        >
          Aggiungi
        </Button>
        {add.isError && <Alert>L'utensile non è stato aggiunto: riprova tra poco.</Alert>}
      </form>

      {list.isError ? (
        <div className="pt-3">
          <ErrorState
            message="Gli utensili non si caricano."
            onRetry={() => list.refetch()}
            retrying={list.isFetching}
          />
        </div>
      ) : list.data && list.data.length === 0 ? (
        <p className="pt-3 text-sm text-ink-soft">
          Scrivi gli strumenti che hai in cucina: le ricette scritte dall'AI useranno solo quelli
        </p>
      ) : list.data ? (
        <ul className="divide-y divide-line pt-3">
          {list.data.map((utensil) => (
            <UtensilRow key={utensil.id} utensil={utensil} />
          ))}
        </ul>
      ) : null}
    </Screen>
  );
}

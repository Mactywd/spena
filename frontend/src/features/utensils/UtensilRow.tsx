import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { useNotice } from "../../components/ui/noticeContext";
import type { Utensil } from "../../domain/types";
import { UTENSILS_KEY, createUtensil, deleteUtensil, patchUtensil } from "./api";

function isNotFound(error: unknown) {
  return error instanceof ApiError && error.status === 404;
}

/** Una riga dell'elenco: a riposo nome e nota con «Correggi» e «Togli»; con «Correggi»
 * aperto, al suo posto un modulo coi due campi già pieni. */
export function UtensilRow({ utensil }: { utensil: Utensil }) {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(utensil.name);
  const [note, setNote] = useState(utensil.note ?? "");
  const invalidate = () => queryClient.invalidateQueries({ queryKey: UTENSILS_KEY });
  const nameRef = useRef<HTMLInputElement>(null);
  const correctRef = useRef<HTMLButtonElement>(null);
  // il valore di `editing` al giro prima: il fuoco torna su «Correggi» solo al passaggio
  // da vero a falso, mai al primo montaggio
  const wasEditing = useRef(false);

  useEffect(() => {
    if (editing) nameRef.current?.focus();
    else if (wasEditing.current) correctRef.current?.focus();
    wasEditing.current = editing;
  }, [editing]);

  const save = useMutation({
    mutationFn: () => patchUtensil(utensil.id, { name, note: note === "" ? null : note }),
    onSuccess: async () => {
      setEditing(false);
      await invalidate();
    },
    // un utensile già sparito: l'elenco riletto non ha più questa riga
    // la riga sparirà con l'elenco riletto, e un Alert dentro di lei con lei: lo dice l'avviso
    onError: async (error) => {
      if (!isNotFound(error)) return;
      notice({ text: "Questo utensile non c'è più." });
      await invalidate();
    },
  });

  const remove = useMutation({
    mutationFn: async () => {
      try {
        await deleteUtensil(utensil.id);
      } catch (error) {
        // già tolto altrove: lo scopo è raggiunto
        if (!isNotFound(error)) throw error;
      }
    },
    onSuccess: async () => {
      // il testo e l'azione non dipendono dalla riga, che sparisce con l'invalidazione
      const { name: oldName, note: oldNote } = utensil;
      await invalidate();
      notice({
        text: `Tolto «${oldName}».`,
        action: {
          label: "Annulla",
          onClick: () => {
            createUtensil({ name: oldName, note: oldNote })
              .then(invalidate)
              .catch(() =>
                notice({ text: `«${oldName}» non è tornato: riscrivilo qui sopra.` })
              );
          },
        },
      });
    },
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    if (name.trim() === "" || save.isPending) return;
    save.mutate();
  }

  if (editing) {
    return (
      <li className="py-2">
        <form onSubmit={submit} className="flex flex-col items-start gap-3">
          <label className="block w-full text-sm font-medium text-ink-soft">
            Nome
            <input
              ref={nameRef}
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={120}
              className="mt-1.5"
            />
          </label>
          <label className="block w-full text-sm font-medium text-ink-soft">
            Nota
            <input
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={200}
              className="mt-1.5"
            />
          </label>
          <div className="flex flex-col items-start gap-2">
            <Button
              type="submit"
              variant="primary"
              busy={save.isPending}
              unavailableReason={name.trim() === "" ? "Scrivi il nome dell'utensile." : undefined}
            >
              Salva
            </Button>
            <Button variant="ghost" onClick={() => setEditing(false)}>
              Annulla
            </Button>
          </div>
          {save.isError && !isNotFound(save.error) && (
            <Alert>La correzione non è stata salvata: riprova tra poco.</Alert>
          )}
        </form>
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-1 py-1">
      <div className="flex min-h-11 items-center justify-between gap-2">
        <span className="min-w-0 flex-1 break-words">
          {utensil.name}
          {utensil.note && (
            <span className="block text-xs text-ink-soft">{utensil.note}</span>
          )}
        </span>
        <span className="flex shrink-0 gap-1">
          <Button
            ref={correctRef}
            variant="ghost"
            accessibleName={`Correggi «${utensil.name}»`}
            onClick={() => {
              setName(utensil.name);
              setNote(utensil.note ?? "");
              save.reset();
              setEditing(true);
            }}
          >
            Correggi
          </Button>
          <Button
            variant="danger"
            busy={remove.isPending}
            accessibleName={`Togli «${utensil.name}»`}
            onClick={() => remove.mutate()}
          >
            Togli
          </Button>
        </span>
      </div>
      {remove.isError && <Alert>L'utensile non è stato tolto: riprova tra poco.</Alert>}
    </li>
  );
}

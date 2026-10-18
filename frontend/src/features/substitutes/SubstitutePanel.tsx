import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { loadLineSubstitution, resetLineSubstitution, saveLineSubstitution } from "./api";
import { SubstituteAnswer } from "./SubstituteAnswer";
import { SubstituteEditor } from "./SubstituteEditor";
import type { LineSubstitution } from "./types";
import { provenanceText } from "./wording";

/** La chiave della risposta di una riga: l'Anagrafica invalida `["substitution"]` quando
 * cambia una voce generale. */
function substitutionKey(recipeId: string, ingredientId: string) {
  return ["substitution", recipeId, ingredientId] as const;
}

/** Sotto una riga d'ingrediente, cosa usare al suo posto (R5).
 *
 * Legge la risposta che vale per la riga; se non c'è, il server la chiede all'AI adesso
 * e la salva (`loadLineSubstitution`). Se l'AI non risponde, «Nessun suggerimento
 * ancora.» con «Riprova» e «Scrivi tu»: mai un vicolo cieco. Da qui si scrive solo la
 * correzione di questa ricetta; la voce generale si corregge in Anagrafica. */
export function SubstitutePanel({
  recipeId,
  ingredientId,
  ingredientName,
}: {
  recipeId: string;
  ingredientId: string;
  ingredientName: string;
}) {
  const queryClient = useQueryClient();
  const key = substitutionKey(recipeId, ingredientId);
  const [editing, setEditing] = useState(false);
  const query = useQuery({ queryKey: key, queryFn: () => loadLineSubstitution(recipeId, ingredientId) });
  const reset = useMutation({
    mutationFn: () => resetLineSubstitution(recipeId, ingredientId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  // Chiuso il modulo — salvato o annullato — il fuoco torna sul pulsante che apre il
  // modulo: quello che l'aveva si è smontato col modulo, e cadrebbe sul `body`. Un `ref`
  // e non uno stato: è un'intenzione per il prossimo disegno (la stessa forma di «Cucina»).
  const actionRef = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (editing || !refocus.current) return;
    refocus.current = false;
    actionRef.current?.focus();
  }, [editing]);
  function closeEditor() {
    refocus.current = true;
    setEditing(false);
  }

  let body: ReactNode;
  if (query.isPending) {
    body = (
      <p role="status" className="text-sm text-ink-soft">
        {`Cerco cosa usare al posto di ${ingredientName}…`}
      </p>
    );
  } else if (query.isError) {
    // una riga che non c'è più (la ricetta è cambiata) non torna riprovando
    const gone = query.error instanceof ApiError && query.error.status === 404;
    body = (
      <div className="flex flex-col items-start gap-2">
        <Alert>
          {gone
            ? "Questo ingrediente non è più nella ricetta: ricarica la pagina."
            : "Non sono riuscito a leggere i sostituti."}
        </Alert>
        {!gone && (
          <Button busy={query.isFetching} onClick={() => void query.refetch()}>
            Riprova
          </Button>
        )}
      </div>
    );
  } else if (editing) {
    body = (
      <SubstituteEditor
        legend={`Al posto di ${ingredientName}, in questa ricetta:`}
        saveLabel="Salva per questa ricetta"
        initialVerdict={query.data.verdict}
        initialSubstitutes={query.data.substitutes}
        save={(answer) => saveLineSubstitution(recipeId, ingredientId, answer)}
        onSaved={(saved: LineSubstitution) => {
          queryClient.setQueryData(key, saved);
          closeEditor();
        }}
        onCancel={closeEditor}
      />
    );
  } else if (query.data.verdict === null) {
    body = (
      <>
        <p className="text-sm text-ink-soft">Nessun suggerimento ancora.</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button busy={query.isFetching} onClick={() => void query.refetch()}>
            Riprova
          </Button>
          <Button ref={actionRef} onClick={() => setEditing(true)}>
            Scrivi tu
          </Button>
        </div>
      </>
    );
  } else {
    const data = query.data;
    // il ramo sopra ha escluso `null`: TypeScript lo sa su `query.data.verdict`, non su `data`
    const verdict = query.data.verdict;
    body = (
      <>
        <SubstituteAnswer ingredientName={ingredientName} verdict={verdict} substitutes={data.substitutes} />
        <p className="pt-1 text-xs text-ink-faint">{provenanceText(data)}</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button ref={actionRef} onClick={() => setEditing(true)}>
            {data.scope === "recipe" ? "Cambia" : "Non va bene qui"}
          </Button>
          {data.scope === "recipe" && (
            <Button variant="ghost" busy={reset.isPending} onClick={() => reset.mutate()}>
              Torna al suggerimento generale
            </Button>
          )}
        </div>
        {reset.isError && (
          <Alert className="pt-2">Non sono riuscito a tornare al suggerimento generale. Riprova.</Alert>
        )}
      </>
    );
  }

  // rientrato sotto il nome: il pallino della riga è largo 12 px, più lo spazio
  return <div className="pt-2 pl-6">{body}</div>;
}

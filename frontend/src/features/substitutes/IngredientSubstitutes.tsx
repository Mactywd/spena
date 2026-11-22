import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { fetchIngredientSubstitutions, saveIngredientSubstitution } from "./api";
import { SubstituteAnswer } from "./SubstituteAnswer";
import { SubstituteEditor } from "./SubstituteEditor";
import type { ContextSubstitution, IngredientSubstitutions, SubstitutionVerdict } from "./types";
import { contextIn, contextTitle, overridesText, recipesText, saveErrorText } from "./wording";

/** «Sostituti» nella scheda di un ingrediente (R5): una scheda per contesto, la voce
 * dell'AI segnata da rivedere — sul modello delle decisioni della coda —, la voce scritta
 * a mano, e quante ricette hanno una correzione loro. Qui si scrive la voce generale;
 * le correzioni delle ricette si scrivono nelle ricette. */
export function IngredientSubstitutes({
  ingredientId,
  ingredientName,
}: {
  ingredientId: string;
  ingredientName: string;
}) {
  const queryClient = useQueryClient();
  const key = ["registry", "substitutes", ingredientId] as const;
  const query = useQuery({ queryKey: key, queryFn: () => fetchIngredientSubstitutions(ingredientId) });

  function saved(data: IngredientSubstitutions) {
    queryClient.setQueryData(key, data);
    // i pannelli delle ricette rileggono: la voce generale è cambiata
    void queryClient.invalidateQueries({ queryKey: ["substitution"] });
  }

  let content: ReactNode;
  if (query.isPending) {
    content = <p className="px-1 text-sm text-ink-soft">Carico…</p>;
  } else if (query.isError) {
    content = (
      <div className="flex flex-col items-start gap-2 px-1">
        <p className="text-sm text-ink-soft">Non sono riuscito a leggere i sostituti.</p>
        <Button
          accessibleName="Riprova a leggere i sostituti"
          busy={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Riprova
        </Button>
      </div>
    );
  } else if (query.data.contexts.length === 0) {
    content = (
      <p className="px-1 text-sm text-ink-soft">
        Non è in nessuna ricetta: i sostituti servono dentro una ricetta.
      </p>
    );
  } else {
    const overrides = overridesText(query.data.recipe_overrides);
    content = (
      <>
        {query.data.contexts.map((item) => (
          <ContextCard
            key={item.context}
            ingredientId={ingredientId}
            ingredientName={ingredientName}
            item={item}
            onSaved={saved}
          />
        ))}
        {overrides && <p className="px-1 text-sm text-ink-soft">{overrides}</p>}
      </>
    );
  }

  return (
    <section>
      <SectionHeading>Sostituti</SectionHeading>
      {content}
    </section>
  );
}

function ContextCard({
  ingredientId,
  ingredientName,
  item,
  onSaved,
}: {
  ingredientId: string;
  ingredientName: string;
  item: ContextSubstitution;
  onSaved: (data: IngredientSubstitutions) => void;
}) {
  const [editing, setEditing] = useState(false);
  const where = contextIn(item.context);
  // «Va bene così» rimanda la risposta com'è: il server la scrive scelta a mano
  const confirm = useMutation({
    mutationFn: (verdict: SubstitutionVerdict) =>
      saveIngredientSubstitution(ingredientId, item.context, {
        verdict,
        substitutes: item.substitutes.map((substitute) => ({
          ingredient_id: substitute.ingredient_id,
          note: substitute.note,
        })),
      }),
    onSuccess: (data) => onSaved(data),
  });

  // chiuso il modulo, il fuoco torna sul pulsante che lo apre (come nel pannello della ricetta)
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
  if (editing) {
    body = (
      <div className="pt-2">
        <SubstituteEditor
          legend={`Al posto di ${ingredientName}, ${where}:`}
          saveLabel="Salva"
          initialVerdict={item.verdict}
          initialSubstitutes={item.substitutes}
          save={(answer) => saveIngredientSubstitution(ingredientId, item.context, answer)}
          onSaved={(data: IngredientSubstitutions) => {
            onSaved(data);
            closeEditor();
          }}
          onCancel={closeEditor}
        />
      </div>
    );
  } else if (item.verdict === null) {
    body = (
      <>
        <p className="pt-1 text-sm text-ink-soft">
          Nessun suggerimento ancora: lo chiedo all'AI la prima volta che lo sostituisci in una ricetta.
        </p>
        <div className="pt-2">
          <Button ref={actionRef} accessibleName={`Scrivi tu: ${where}`} onClick={() => setEditing(true)}>
            Scrivi tu
          </Button>
        </div>
      </>
    );
  } else {
    const verdict = item.verdict;
    body = (
      <>
        <div className="pt-1">
          <SubstituteAnswer ingredientName={ingredientName} verdict={verdict} substitutes={item.substitutes} />
        </div>
        {/* l'ambra di «funziona, ma non del tutto»: una risposta c'è, e non l'ha ancora
            guardata nessuno */}
        {item.decided_by === "ai" ? (
          <p className="pt-1 text-xs font-medium text-low">Deciso dall'AI: da rivedere.</p>
        ) : (
          <p className="pt-1 text-xs text-ink-faint">Scelto a mano.</p>
        )}
        <div className="flex flex-wrap gap-2 pt-2">
          {item.decided_by === "ai" && (
            <Button
              accessibleName={`Va bene così: ${where}`}
              busy={confirm.isPending}
              onClick={() => confirm.mutate(verdict)}
            >
              Va bene così
            </Button>
          )}
          <Button
            ref={actionRef}
            accessibleName={`Correggi: ${where}`}
            onClick={() => {
              // l'errore di un «Va bene così» fallito non deve sopravvivere alla correzione
              confirm.reset();
              setEditing(true);
            }}
          >
            Correggi
          </Button>
        </div>
        {confirm.isError && <Alert className="pt-2">{saveErrorText(confirm.error)}</Alert>}
      </>
    );
  }

  return (
    <Card className="mb-2">
      <h3 className="text-sm font-semibold">
        {contextTitle(item.context)}{" "}
        <span className="font-normal text-ink-faint">{`· ${recipesText(item.recipes)}`}</span>
      </h3>
      {body}
    </Card>
  );
}

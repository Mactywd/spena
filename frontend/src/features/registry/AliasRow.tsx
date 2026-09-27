import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { AliasEntry, Ingredient } from "../../domain/types";
import { deleteAlias, moveAlias, refreshAfterCorrection, registryRefusal } from "./api";

/** Un alias della scheda. Quelli che sono la metà di una decisione della coda non si
 * toccano da qui: dicono «Deciso nella coda» e portano lì (spec §4). Gli altri si
 * spostano sotto un altro ingrediente o si tolgono. */
export function AliasRow({ ingredientId, alias }: { ingredientId: string; alias: AliasEntry }) {
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState(false);
  const move = useMutation({
    mutationFn: (target: Ingredient) => moveAlias(ingredientId, alias.id, target.id),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const remove = useMutation({
    mutationFn: () => deleteAlias(ingredientId, alias.id),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const busy = move.isPending || remove.isPending;
  const failed = move.error ?? remove.error;
  const refusal = registryRefusal(failed);

  return (
    <li className="flex flex-col gap-2 py-1">
      <div className="flex min-h-11 items-center justify-between gap-2">
        <span className="min-w-0 truncate">{alias.alias}</span>
        {alias.decided_in_queue ? (
          <Link
            to="/ricette/importa"
            className="inline-flex min-h-11 shrink-0 items-center font-medium text-brand"
          >
            Deciso nella coda
          </Link>
        ) : (
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              aria-expanded={moving}
              aria-label={`Sposta l'alias «${alias.alias}»`}
              onClick={() => setMoving((open) => !open)}
              className={buttonClasses("ghost")}
            >
              Sposta
            </button>
            <button
              type="button"
              disabled={busy}
              aria-label={`Togli l'alias «${alias.alias}»`}
              onClick={() => remove.mutate()}
              className={buttonClasses("danger")}
            >
              Togli
            </button>
          </span>
        )}
      </div>
      {moving && (
        <IngredientPicker
          label={`Sposta «${alias.alias}» sotto`}
          failureNote="L'alias resta dov'è: riprova tra poco."
          disabled={busy}
          onPick={(target) => {
            setMoving(false);
            move.mutate(target);
          }}
        />
      )}
      {refusal?.code === "import_alias" && (
        <Alert>
          {refusal.detail}{" "}
          <Link to="/ricette/importa" className="font-medium text-brand">
            Vai alla coda
          </Link>
        </Alert>
      )}
      {refusal !== null && refusal.code !== "import_alias" && <Alert>{refusal.detail}</Alert>}
      {failed && refusal === null && (
        <Alert>Non sono riuscito a correggere l'alias. È ancora qui: riprova.</Alert>
      )}
    </li>
  );
}

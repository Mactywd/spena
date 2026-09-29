import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconArrowsTransferDown, IconBarcodeOff } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";
import { InlineField } from "./InlineField";
import {
  deleteProduct,
  fetchProductDetail,
  patchProduct,
  refreshAfterCorrection,
  registryRefusal,
  type ProductPatchBody,
} from "./api";
import { backFrom, ingredientPath, originFrom } from "./origin";
import { movedText, pantryText } from "./wording";

/** La scheda del prodotto (spec S9 §6.4). È anche la scheda dell'elemento di dispensa:
 * dalla riga della dispensa si arriva qui, e l'ingrediente sta come link. Il caso del
 * parmigiano sotto «burro» sono due tocchi e una scelta.
 *
 * `key` sull'id, per la stessa ragione della scheda dell'ingrediente. */
export function ProductScreen() {
  const { id = "" } = useParams();
  return <ProductCard key={id} id={id} />;
}

function ProductCard({ id }: { id: string }) {
  const [params] = useSearchParams();
  const origin = originFrom(params.get("da"));
  const back = backFrom(origin);
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState(false);
  const [movedNote, setMovedNote] = useState<string | null>(null);

  const {
    data: product,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["registry", "product", id],
    queryFn: () => fetchProductDetail(id),
  });
  const patch = useMutation({
    mutationFn: (body: ProductPatchBody) => patchProduct(id, body),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const move = useMutation({
    mutationFn: (target: Ingredient) => patchProduct(id, { ingredient_id: target.id }),
    onSuccess: async (updated) => {
      setMoving(false);
      setMovedNote(movedText(updated));
      await refreshAfterCorrection(queryClient);
    },
  });
  const navigate = useNavigate();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // le due uscite dei rifiuti del codice, e «Togli il codice»: una mutazione sua, così
  // un suo guasto si dice senza confondersi con quello del campo
  const barcodeAction = useMutation({
    mutationFn: (body: ProductPatchBody) => patchProduct(id, body),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const remove = useMutation({
    mutationFn: () => deleteProduct(id),
    onSuccess: () => {
      // si va via: segnare vecchio senza rileggere, perché questa scheda non c'è più
      void refreshAfterCorrection(queryClient, false);
      navigate(back.to);
    },
  });

  /** Il guasto di `barcodeAction` (non un rifiuto: quello lo dice `barcodeRefusal`),
   * con parole che dicono l'azione tentata invece di un generico «è ancora quello di
   * prima» — che per «Sposta il codice qui» o «Usalo lo stesso» falliti non descrive
   * quel che è successo, solo che il campo non è cambiato (rilievo della revisione
   * finale S9). Letto dalle `variables` dell'ultima mutazione, non da uno stato a
   * parte: sono già quel che si è tentato di mandare. */
  function barcodeActionFailureText(variables: ProductPatchBody | undefined): string {
    if (variables?.take_barcode) return "Non sono riuscito a spostare il codice qui. Riprova.";
    if (variables?.accept_bad_checksum) return "Non sono riuscito a usare il codice lo stesso. Riprova.";
    return "Non sono riuscito a togliere il codice. È ancora qui: riprova.";
  }

  /** Il rifiuto del codice con la sua uscita (spec §7): un codice già usato si sposta
   * qui, un codice che non torna si usa lo stesso. */
  function barcodeRefusal(failure: unknown, draft: string) {
    const refusal = registryRefusal(failure);
    if (refusal?.code === "barcode_taken") {
      return (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">Il codice è di «{refusal.existing.name}». Spostalo qui?</span>
          <Button
            variant="warn"
            busy={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, take_barcode: true })}
          >
            Sposta il codice qui
          </Button>
        </div>
      );
    }
    if (refusal?.code === "bad_checksum") {
      return (
        // ambra e non rosso: non è un rifiuto, è un avviso (S20)
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-low">{refusal.detail}</span>
          <Button
            busy={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, accept_bad_checksum: true })}
          >
            Usalo lo stesso
          </Button>
        </div>
      );
    }
    return (
      <Alert>
        {refusal
          ? refusal.detail
          : "Non sono riuscito a salvare il codice. Quel che hai scritto è ancora qui: riprova."}
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <Screen title="Prodotto" back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !product) {
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <Screen title="Prodotto" back={back}>
        <Alert>
          {gone
            ? "Questo prodotto non c'è più. Gli elementi di dispensa che lo avevano sono rimasti, sfusi."
            : "Non sono riuscito a leggere questo prodotto."}
        </Alert>
        {!gone && (
          <button
            type="button"
            onClick={() => void refetch()}
            className={`${buttonClasses("secondary")} mt-3`}
          >
            Riprova
          </button>
        )}
      </Screen>
    );
  }

  return (
    <Screen
      title={product.name}
      subtitle={product.brand ?? undefined}
      back={back}
      // le correzioni accanto al titolo, come quelle dell'ingrediente (spec T3 §4.7): più
      // pulsanti in gruppo → solo icone, coi nomi di prima come `aria-label` (spec §6).
      // «Togli il codice» c'è solo se c'è un codice da togliere, come prima
      action={
        <IconToolbar label="Correzioni del prodotto">
          <Button
            variant="ghost"
            icon={IconArrowsTransferDown}
            label="Spostalo"
            aria-expanded={moving}
            onClick={() => setMoving((open) => !open)}
          />
          {product.barcode && (
            <Button
              variant="ghost"
              icon={IconBarcodeOff}
              label="Togli il codice"
              // `busy` e non `disabled` (Consegna 6a): chi l'ha premuto da tastiera
              // tiene il fuoco finché la richiesta è in volo
              busy={barcodeAction.isPending}
              onClick={() => barcodeAction.mutate({ barcode: null })}
            />
          )}
        </IconToolbar>
      }
    >
      {movedNote && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {movedNote}
        </p>
      )}

      {/* lo spostamento si apre qui, sotto l'intestazione, come i pannelli della scheda
          dell'ingrediente. Senza filtro sul `kind`: in anagrafica si corregge anche il
          non alimentare */}
      {moving && (
        <Card as="section" className="mb-3 flex flex-col gap-2">
          <IngredientPicker
            label="Sposta sotto"
            failureNote="Il prodotto resta dov'è: riprova tra poco."
            disabled={move.isPending}
            onPick={(target) => move.mutate(target)}
          />
        </Card>
      )}
      {move.isError && (
        <div className="pb-3">
          <Alert>
            Non sono riuscito a spostarlo: è ancora sotto «{product.ingredient.display_name}». Riprova.
          </Alert>
        </div>
      )}

      <Card className="flex flex-col gap-3">
        {/* obbligatorio (F17): il nome non può restare nullo in colonna */}
        <InlineField
          label="Nome"
          value={product.name}
          required
          onSave={(next) => patch.mutateAsync({ name: next })}
        />
        {/* non obbligatoria: una marca vuota è una richiesta valida, toglierla */}
        <InlineField
          label="Marca"
          value={product.brand ?? ""}
          placeholder="Nessuna marca"
          onSave={(next) => patch.mutateAsync({ brand: next === "" ? null : next })}
        />
      </Card>

      <SectionHeading>Codice a barre</SectionHeading>
      <Card className="flex flex-col gap-2">
        <InlineField
          label="Codice"
          value={product.barcode ?? ""}
          placeholder="Nessun codice"
          inputMode="numeric"
          onSave={(next) => patch.mutateAsync({ barcode: next === "" ? null : next })}
          describeError={barcodeRefusal}
        />
        {product.valid_checksum === false && (
          <p className="text-xs text-ink-faint">
            La cifra di controllo di questo codice non torna: può essere un codice del negozio.
          </p>
        )}
        {barcodeAction.isError && <Alert>{barcodeActionFailureText(barcodeAction.variables)}</Alert>}
      </Card>

      <SectionHeading>Ingrediente</SectionHeading>
      <Card className="flex flex-col gap-2">
        <Link
          to={ingredientPath(product.ingredient.id, origin)}
          className="inline-flex min-h-11 items-center font-medium text-brand"
        >
          {product.ingredient.display_name}
        </Link>
        <p className="text-xs text-ink-faint">{pantryText(product.pantry_items.length)}</p>
      </Card>

      <div className="pt-6">
        {!confirmingDelete ? (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className={buttonClasses("danger")}
          >
            Elimina il prodotto
          </button>
        ) : (
          <div
            role="alertdialog"
            aria-label="Conferma l'eliminazione"
            className="flex flex-col gap-2 rounded-card bg-card p-3"
          >
            <p className="text-sm">
              Gli elementi in dispensa restano, come «{product.ingredient.display_name}» sfuso.
            </p>
            <div className="flex flex-wrap gap-2">
              {/* `busy` e non `disabled` (Consegna 6a): il fuoco resta su «Elimina» */}
              <Button variant="danger" busy={remove.isPending} onClick={() => remove.mutate()}>
                Elimina
              </Button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className={buttonClasses("ghost")}
              >
                Lascia
              </button>
            </div>
            {remove.isError && <Alert>Non sono riuscito a eliminarlo. È ancora qui: riprova.</Alert>}
          </div>
        )}
      </div>
    </Screen>
  );
}

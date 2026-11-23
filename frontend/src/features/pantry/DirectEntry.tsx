import { useRef, useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { EntryCard } from "./EntryCard";
import { addPantryItem } from "./api";
import { entryLabel, entryTitle, type EntryChoice } from "./entryView";
import { Button } from "../../components/ui/Button";
import { IconX } from "../../components/ui/icons";
import { IngredientChooser } from "../stocking/IngredientChooser";
import { ProductResolver } from "../stocking/ProductResolver";
import type { PantryItem } from "../../domain/types";

/** Da dove si entra: il + col testo della barra (uno sfuso, o quando il codice non c'è),
 * o «Scansiona» (la confezione in mano). */
export type EntryDoor = { kind: "plus"; text: string } | { kind: "scan" };

type Stage =
  // dal +: quale ingrediente
  | { kind: "choose" }
  // il codice o il catalogo, con l'ingrediente della scheda (`base`) o senza (la scansione)
  | { kind: "resolve"; start: "scanner" | "catalog"; base: EntryChoice | null; serial: number }
  // la scheda di conferma
  | { kind: "confirm"; choice: EntryChoice; serial: number };

/**
 * L'ingresso diretto in dispensa (S3, decisioni di Mattia del 2026-10-07): le stesse
 * strade e le stesse guardie di «Sistema la spesa», senza una voce di lista.
 *
 * - **«Scansiona»**: lo scanner senza ingrediente atteso; un prodotto a catalogo va
 *   dritto alla scheda (due tocchi: il codice e «Metti in dispensa»), un codice nuovo
 *   passa da «Di che ingrediente è?» e dal modulo (`ProductResolver`). Dopo «Metti in
 *   dispensa» il pannello non si chiude: torna allo scanner per il codice dopo — il
 *   censimento della dispensa è il secondo caso della richiesta, e riaprirlo a ogni
 *   confezione è il gesto che lo rende lento.
 * - **Il +**: l'ingrediente col testo della barra, che si può creare lì; la scheda
 *   sfusa offre il codice e il catalogo, con l'ingrediente atteso. Dopo «Metti in
 *   dispensa» si chiude, come prima.
 *
 * La scrittura passa da qui; cosa fare dopo (la riga in vista, l'avviso con «Annulla»)
 * lo decide la Dispensa in `onEntered`.
 */
export function DirectEntry({
  door,
  onEntered,
  onClose,
  undoneItemIds,
}: {
  door: EntryDoor;
  /** Le voci di questa serie che la Dispensa ha già annullato: la nota non le conta. */
  undoneItemIds: ReadonlySet<string>;
  onEntered: (created: PantryItem, label: string) => void;
  onClose: () => void;
}) {
  const serial = useRef(0);
  const [stage, setStage] = useState<Stage>(() =>
    door.kind === "plus"
      ? { kind: "choose" }
      : { kind: "resolve", start: "scanner", base: null, serial: 0 }
  );
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  // il codice letto e rimasto senza prodotto (S8): sopravvive al resolver che si chiude,
  // per il catalogo aperto dopo dalla stessa scheda. Quando seguirlo lo decide il resolver
  const [rememberedCode, setRememberedCode] = useState<string | undefined>(undefined);
  // l'ultima voce entrata in questa serie, col suo prodotto: riletto subito, la scheda lo
  // dice, salvo che la voce sia stata annullata nel frattempo
  const [lastEntered, setLastEntered] = useState<{ itemId: string; productId: string | null } | null>(
    null
  );

  const add = useMutation({
    mutationFn: ({ choice, expiresOn }: { choice: EntryChoice; expiresOn: string | null }) =>
      addPantryItem({
        ingredientId: choice.ingredient.id,
        productId: choice.product?.id ?? null,
        expiresOn,
        // solo un prodotto scelto a catalogo dopo un codice letto lo porta (S8)
        barcode: (choice.product && choice.barcode) || null,
      }),
    // nelle opzioni e non in `mutate`: la voce è in dispensa anche se il pannello si è
    // chiuso nel frattempo, e la Dispensa deve saperlo (la riga, l'avviso con «Annulla»)
    onSuccess: (created, { choice }) => onEntered(created, entryLabel(choice)),
  });

  function next(): number {
    serial.current += 1;
    return serial.current;
  }

  function confirm(choice: EntryChoice) {
    add.reset();
    setStage({ kind: "confirm", choice, serial: next() });
  }

  /** Un giro nuovo della scansione: un'altra confezione, senza niente di quella prima. */
  function scanAgain() {
    add.reset();
    setExpiry(undefined);
    setRememberedCode(undefined);
    setStage({ kind: "resolve", start: "scanner", base: null, serial: next() });
  }

  function chooseAgain() {
    add.reset();
    setExpiry(undefined);
    setRememberedCode(undefined);
    setStage({ kind: "choose" });
  }

  /** «Cambia» torna indietro di un passo: dalla scansione a un codice nuovo; dal + con
   * un prodotto alla stessa voce sfusa; dal + sfuso alla scelta dell'ingrediente. */
  function change(choice: EntryChoice) {
    if (door.kind === "scan") {
      scanAgain();
      return;
    }
    if (choice.product) {
      confirm({ ingredient: choice.ingredient, product: null });
      return;
    }
    chooseAgain();
  }

  function submit(choice: EntryChoice) {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (add.isPending) return;
    add.mutate(
      { choice, expiresOn: expiry || null },
      {
        onSuccess: (created) => {
          if (door.kind === "plus") {
            onClose();
            return;
          }
          setLastEntered({ itemId: created.id, productId: choice.product?.id ?? null });
          scanAgain();
        },
      }
    );
  }

  let body: ReactNode;
  if (stage.kind === "choose") {
    body = (
      <IngredientChooser
        label="Ingrediente da mettere in dispensa"
        failureNote="Puoi comunque aggiungerlo."
        initialTerm={door.kind === "plus" ? door.text : ""}
        onChosen={(ingredient) =>
          confirm({
            ingredient: { id: ingredient.id, name: ingredient.name, kind: ingredient.kind },
            product: null,
          })
        }
      />
    );
  } else if (stage.kind === "resolve") {
    const { base } = stage;
    body = (
      <ProductResolver
        key={stage.serial}
        label={base ? entryTitle(base) : null}
        ingredient={base?.ingredient ?? null}
        start={stage.start}
        rememberedCode={rememberedCode}
        onRememberCode={(code) => setRememberedCode(code ?? undefined)}
        onResolved={(resolution, ingredient) =>
          confirm(
            resolution.kind === "product"
              ? { ingredient, product: resolution.product, barcode: resolution.barcode }
              : { ingredient, product: null }
          )
        }
        // dal +, annullare torna alla scheda; dalla scansione chiude, come la ✕
        onCancel={() => (base ? confirm(base) : onClose())}
      />
    );
  } else {
    const { choice } = stage;
    const justEntered =
      door.kind === "scan" &&
      choice.product !== null &&
      lastEntered !== null &&
      choice.product.id === lastEntered.productId &&
      !undoneItemIds.has(lastEntered.itemId);
    const loosePlus = door.kind === "plus" && choice.product === null;
    body = (
      <EntryCard
        key={stage.serial}
        choice={choice}
        expiry={expiry}
        onExpiry={setExpiry}
        busy={add.isPending}
        failed={add.isError}
        justEntered={justEntered}
        onCode={
          loosePlus
            ? () => setStage({ kind: "resolve", start: "scanner", base: choice, serial: next() })
            : undefined
        }
        onCatalog={
          loosePlus
            ? () => setStage({ kind: "resolve", start: "catalog", base: choice, serial: next() })
            : undefined
        }
        onChange={() => change(choice)}
        onConfirm={() => submit(choice)}
        onCancel={() => (door.kind === "plus" ? onClose() : scanAgain())}
      />
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-2xl bg-card p-3">
      <div className="min-w-0 flex-1">{body}</div>
      <Button variant="ghost" icon={IconX} label="Chiudi l'aggiunta" onClick={onClose} />
    </div>
  );
}

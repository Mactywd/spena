import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { createProduct } from "./api";
import type { BarcodeLookup, Product } from "../../domain/types";
import { buttonClasses } from "../../components/ui/buttonClasses";

const EMPTY_NUTRIENTS: Record<string, string> = { kcal: "", protein: "", carbs: "", fat: "" };

const FIELDS: [string, string][] = [
  ["kcal", "Calorie per 100 g"],
  ["protein", "Proteine"],
  ["carbs", "Carboidrati"],
  ["fat", "Grassi"],
];

// i nutrienti che Open Food Facts riporta oltre ai quattro modificabili: non si
// mostrano (sono quattro campi in più da leggere su un telefono, per dati che
// nessuno correggerà a mano) ma vanno nominati, perché vengono salvati
const EXTRA_LABELS: Record<string, string> = {
  sugars: "zuccheri",
  saturated_fat: "grassi saturi",
  fiber: "fibre",
  salt: "sale",
};

/** Quel che Open Food Facts ha già detto su un codice a barre non ancora in
 * catalogo: non lo reinventiamo da zero, lo si precompila e si lascia
 * all'utente confermare o correggere. Derivato dalla forma che il backend
 * manda: una copia a mano si scollerebbe al primo campo nuovo. */
export type ProductSuggestion = NonNullable<BarcodeLookup["suggestion"]>;

function seedNutrients(suggestion?: ProductSuggestion | null): Record<string, string> {
  // tutta la mappa, non solo i quattro campi visibili: la conferma è l'unico
  // momento in cui quei valori esistono, e quel che non si riporta è perso per
  // sempre. Un nutriente assente resta vuoto e non diventa zero, perché zero
  // sarebbe un'affermazione e non lo è.
  const seeded = { ...EMPTY_NUTRIENTS };
  for (const [key, value] of Object.entries(suggestion?.nutrients ?? {})) {
    if (typeof value === "number") seeded[key] = String(value);
  }
  return seeded;
}

/** La valvola di sfogo: Open Food Facts copre male discount e marchi regionali. */
export function CustomProductForm({
  ingredientId,
  itemLabel,
  barcode,
  suggestion,
  onCreated,
  onCancel,
}: {
  ingredientId: string;
  itemLabel: string;
  barcode?: string;
  suggestion?: ProductSuggestion | null;
  onCreated: (product: Product) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(suggestion?.name ?? "");
  const [brand, setBrand] = useState(suggestion?.brand ?? "");
  const [nutrients, setNutrients] = useState(() => seedNutrients(suggestion));

  // passa dalla MutationCache come ogni altra scrittura: è quel che riporta
  // all'accesso se la sessione è scaduta nel frattempo
  const create = useMutation({
    mutationFn: () => {
      const parsed = Object.fromEntries(
        Object.entries(nutrients)
          .filter(([, value]) => value !== "")
          .map(([key, value]) => [key, Number(value)])
      );
      return createProduct({
        ingredient_id: ingredientId,
        name,
        brand: brand || undefined,
        barcode: barcode || undefined,
        nutrients: Object.keys(parsed).length > 0 ? parsed : undefined,
        // un prodotto che viene da Open Food Facts non è "custom", e la sua
        // immagine non si recupera più da qui: entrambe si riportano adesso
        source: suggestion ? "openfoodfacts" : undefined,
        image_url: suggestion?.image_url ?? undefined,
      });
    },
    onSuccess: onCreated,
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    // il modulo resta compilato: un 409 (codice già in catalogo) o un servizio
    // giù non devono far perdere quel che l'utente ha scritto
    create.mutate();
  }

  const carried = Object.entries(nutrients).filter(
    ([key, value]) => value !== "" && !FIELDS.some(([field]) => field === key)
  );

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-card bg-card p-4">
      <h3 className="font-semibold">Nuovo prodotto per «{itemLabel}»</h3>
      <label className="text-sm">
        Nome
        <input value={name} onChange={(e) => setName(e.target.value)} required
               className="mt-1.5" />
      </label>
      <label className="text-sm">
        Marca
        <input value={brand} onChange={(e) => setBrand(e.target.value)}
               className="mt-1.5" />
      </label>
      <div className="grid grid-cols-2 gap-2">
        {FIELDS.map(([key, label]) => (
          <label key={key} className="text-sm">
            {label}
            <input
              type="number" inputMode="decimal" step="0.1" value={nutrients[key] ?? ""}
              onChange={(e) => setNutrients((prev) => ({ ...prev, [key]: e.target.value }))}
              className="mt-1.5"
            />
          </label>
        ))}
      </div>
      <p className="text-xs text-ink-soft">
        I valori sono facoltativi. Lasciarli vuoti è meglio che inventarli.
      </p>
      {carried.length > 0 && (
        <p className="text-xs text-ink-soft">
          Da Open Food Facts vengono salvati anche{" "}
          {carried.map(([key]) => EXTRA_LABELS[key] ?? key).join(", ")}.
        </p>
      )}
      {create.isError && (
        <p role="alert" className="text-sm text-danger">
          Non sono riuscito a salvare il prodotto. I dati sono ancora qui: riprova.
        </p>
      )}
      <button type="submit" disabled={create.isPending}
              className={buttonClasses("primary", "block")}>
        Salva prodotto
      </button>
      {/* un 409 persistente non deve incollare il riquadro allo schermo: si esce
          sempre, e la voce resta sistemabile come sfusa */}
      <button type="button" onClick={onCancel} className={`${buttonClasses("ghost")} self-start`}>
        Annulla
      </button>
    </form>
  );
}

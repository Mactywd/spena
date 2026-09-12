import { useState } from "react";
import type { FormEvent } from "react";
import { createProduct } from "./api";
import type { Product } from "../../domain/types";

const EMPTY_NUTRIENTS = { kcal: "", protein: "", carbs: "", fat: "" };

const FIELDS: [keyof typeof EMPTY_NUTRIENTS, string][] = [
  ["kcal", "Calorie per 100 g"],
  ["protein", "Proteine"],
  ["carbs", "Carboidrati"],
  ["fat", "Grassi"],
];

/** Quel che Open Food Facts ha già detto su un codice a barre non ancora in
 * catalogo: non lo reinventiamo da zero, lo si precompila e si lascia
 * all'utente confermare o correggere. */
export interface ProductSuggestion {
  name: string;
  brand: string | null;
  nutrients: Record<string, number>;
}

function seedNutrients(suggestion?: ProductSuggestion | null) {
  if (!suggestion) return EMPTY_NUTRIENTS;
  const seeded = { ...EMPTY_NUTRIENTS };
  for (const [key] of FIELDS) {
    // solo i valori che Open Food Facts ha davvero: un nutriente assente resta
    // vuoto, non diventa zero, perché zero sarebbe un'affermazione e non lo è
    const value = suggestion.nutrients[key];
    if (typeof value === "number") seeded[key] = String(value);
  }
  return seeded;
}

/** La valvola di sfogo: Open Food Facts copre male discount e marchi regionali. */
export function CustomProductForm({
  ingredientId,
  barcode,
  suggestion,
  onCreated,
}: {
  ingredientId: string;
  barcode?: string;
  suggestion?: ProductSuggestion | null;
  onCreated: (product: Product) => void;
}) {
  const [name, setName] = useState(suggestion?.name ?? "");
  const [brand, setBrand] = useState(suggestion?.brand ?? "");
  const [nutrients, setNutrients] = useState(() => seedNutrients(suggestion));
  const [submitting, setSubmitting] = useState(false);
  const [failed, setFailed] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const parsed = Object.fromEntries(
      Object.entries(nutrients)
        .filter(([, value]) => value !== "")
        .map(([key, value]) => [key, Number(value)])
    );
    setFailed(false);
    setSubmitting(true);
    try {
      const product = await createProduct({
        ingredient_id: ingredientId,
        name,
        brand: brand || undefined,
        barcode: barcode || undefined,
        nutrients: Object.keys(parsed).length > 0 ? parsed : undefined,
      });
      onCreated(product);
    } catch {
      // il modulo resta compilato: un 409 (codice già in catalogo) o un servizio
      // giù non devono far perdere quel che l'utente ha scritto
      setFailed(true);
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-lg border p-4">
      <h3 className="font-semibold">Nuovo prodotto</h3>
      <label className="text-sm">
        Nome
        <input value={name} onChange={(e) => setName(e.target.value)} required
               className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <label className="text-sm">
        Marca
        <input value={brand} onChange={(e) => setBrand(e.target.value)}
               className="mt-1 w-full rounded border px-3 py-2" />
      </label>
      <div className="grid grid-cols-2 gap-2">
        {FIELDS.map(([key, label]) => (
          <label key={key} className="text-sm">
            {label}
            <input
              type="number" inputMode="decimal" step="0.1" value={nutrients[key]}
              onChange={(e) => setNutrients({ ...nutrients, [key]: e.target.value })}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
        ))}
      </div>
      <p className="text-xs text-neutral-500">
        I valori sono facoltativi. Lasciarli vuoti è meglio che inventarli.
      </p>
      {failed && (
        <p role="alert" className="text-sm text-red-600">
          Non sono riuscito a salvare il prodotto. I dati sono ancora qui: riprova.
        </p>
      )}
      <button type="submit" disabled={submitting}
              className="rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40">
        Salva prodotto
      </button>
    </form>
  );
}

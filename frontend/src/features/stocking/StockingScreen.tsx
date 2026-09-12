import { useCallback, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchShoppingList, searchIngredients } from "../shopping-list/api";
import { BarcodeScanner } from "./BarcodeScanner";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode, stockItems } from "./api";
import type { Ingredient, Product, ShoppingItem } from "../../domain/types";

type Resolution =
  | { kind: "loose" }
  | { kind: "product"; product: Product };

/**
 * Una voce spuntata ma senza ingrediente abbinato ("un ingrediente che risolve
 * a niente", nelle parole del brief): il testo libero della lista non ha mai
 * trovato un corrispondente. Non può sparire in silenzio dal conto finale, e
 * qui sotto il sistema non inventa niente da solo: l'utente abbina un
 * ingrediente esistente, proprio come quando scrive in lista (Task 18).
 */
function MatchIngredientField({
  rawText,
  onMatched,
}: {
  rawText: string;
  onMatched: (ingredient: Ingredient) => void;
}) {
  const [query, setQuery] = useState(rawText);
  const [suggestions, setSuggestions] = useState<Ingredient[]>([]);
  // sotto 2 caratteri non vale la pena interrogare il backend, come in AddItemField
  const showSuggestions = query.trim().length >= 2;

  useEffect(() => {
    if (!showSuggestions) return;
    // stessa guardia di AddItemField: una ricerca lenta e superata non deve
    // sovrascrivere i suggerimenti di una più recente
    let superseded = false;
    const timer = setTimeout(() => {
      searchIngredients(query)
        .then((found) => {
          if (!superseded) setSuggestions(found);
        })
        .catch(() => {
          if (!superseded) setSuggestions([]);
        });
    }, 180);
    return () => {
      superseded = true;
      clearTimeout(timer);
    };
  }, [query, showSuggestions]);

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3">
      <p className="text-sm text-amber-800">
        «{rawText}» non è abbinata a un ingrediente: scegline uno per poterla sistemare.
      </p>
      <label className="text-sm">
        Abbina un ingrediente
        <input
          aria-label={`Abbina un ingrediente per ${rawText}`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="mt-1 w-full rounded border px-3 py-2"
        />
      </label>
      {showSuggestions && suggestions.length > 0 && (
        <ul role="listbox" className="overflow-hidden rounded-lg border border-neutral-200">
          {suggestions.map((ingredient) => (
            <li key={ingredient.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => onMatched(ingredient)}
                className="w-full px-3 py-2 text-left text-sm"
              >
                {ingredient.display_name}
                <span className="ml-2 text-xs text-neutral-400">{ingredient.category}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function StockingScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: items = [] } = useQuery({
    queryKey: ["shopping-list", "checked"],
    queryFn: () => fetchShoppingList(["checked"]),
  });

  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  const [scanningFor, setScanningFor] = useState<ShoppingItem | null>(null);
  const [manualCode, setManualCode] = useState("");
  const [creatingFor, setCreatingFor] = useState<
    { item: ShoppingItem; barcode: string; suggestion: ProductSuggestion | null } | null
  >(null);

  function effectiveIngredientId(item: ShoppingItem): string | null {
    return item.ingredient_id ?? matchedIngredient[item.id]?.id ?? null;
  }

  const stock = useMutation({
    mutationFn: () =>
      stockItems(
        Object.entries(resolved)
          .map(([itemId, resolution]) => {
            const item = items.find((i) => i.id === itemId);
            const ingredientId = item ? effectiveIngredientId(item) : null;
            if (!ingredientId) return null;
            return {
              shopping_item_id: itemId,
              ingredient_id: ingredientId,
              product_id: resolution.kind === "product" ? resolution.product.id : null,
            };
          })
          .filter((entry): entry is NonNullable<typeof entry> => entry !== null)
      ),
    onSuccess: () => {
      // la lista della spesa tiene in cache le stesse voci: senza invalidare
      // questo prefisso, tornando a "Lista" le voci appena sistemate restano
      // ancora spuntate, come se non fosse successo niente
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      navigate("/dispensa");
    },
  });

  // Senza useCallback, ogni tasto premuto nel campo del codice manuale (un
  // sibling re-render, non legato allo scanner) creerebbe una nuova identità
  // di `onDetected`, e l'effetto di BarcodeScanner ne dipende: la fotocamera
  // si spegnerebbe e si riaccenderebbe a ogni carattere digitato. Le funzioni
  // `set*` di useState sono stabili, quindi usando la forma a updater (non
  // chiudendo su `resolved`) submitCode resta stabile a sua volta.
  const submitCode = useCallback(async (item: ShoppingItem, code: string) => {
    const lookup = await lookupBarcode(code);
    const { product } = lookup;
    if (product) {
      setResolved((prev) => ({ ...prev, [item.id]: { kind: "product", product } }));
      setScanningFor(null);
      return;
    }
    // conosciuto da Open Food Facts ma non ancora in catalogo: il modulo si apre
    // precompilato con quel che si sa già, non da zero. Ignoto anche lì, o
    // servizio giù: stesso modulo, stavolta vuoto — non è mai un vicolo cieco.
    setCreatingFor({ item, barcode: code, suggestion: lookup.suggestion });
    setScanningFor(null);
  }, []);

  const handleDetected = useCallback(
    (code: string) => {
      if (scanningFor) void submitCode(scanningFor, code);
    },
    [scanningFor, submitCode]
  );

  return (
    <div className="p-4">
      <h1 className="pb-3 text-xl font-semibold">Sistema la spesa</h1>

      {items.length === 0 && (
        <p className="text-neutral-500">Niente da sistemare. Spunta prima qualcosa in lista.</p>
      )}

      <ul className="divide-y divide-neutral-100">
        {items.map((item) => {
          const resolution = resolved[item.id];
          const ingredientId = effectiveIngredientId(item);
          return (
            <li key={item.id} className="flex flex-col gap-2 py-3">
              <div className="flex items-center justify-between gap-2">
                <span className={resolution ? "font-medium text-emerald-700" : ""}>
                  {item.raw_text}
                </span>
                {resolution?.kind === "product" && (
                  <span className="text-sm text-neutral-500">{resolution.product.name}</span>
                )}
              </div>

              {!resolution && !ingredientId && (
                <MatchIngredientField
                  rawText={item.raw_text}
                  onMatched={(ingredient) =>
                    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }))
                  }
                />
              )}

              {!resolution && ingredientId && (
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setScanningFor(item)}
                    className="rounded border px-3 py-2 text-sm"
                  >
                    Codice a barre per {item.raw_text}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setResolved((prev) => ({ ...prev, [item.id]: { kind: "loose" } }))
                    }
                    className="rounded border px-3 py-2 text-sm"
                  >
                    Sfuso, senza marca: {item.raw_text}
                  </button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {scanningFor && (
        <div className="mt-4 flex flex-col gap-3 rounded-lg border p-4">
          <BarcodeScanner
            onDetected={handleDetected}
            onCancel={() => setScanningFor(null)}
          />
          <label className="text-sm">
            Codice a barre
            <input
              aria-label="Codice a barre"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitCode(scanningFor, manualCode);
              }}
              className="mt-1 w-full rounded border px-3 py-2"
            />
          </label>
        </div>
      )}

      {creatingFor && effectiveIngredientId(creatingFor.item) && (
        <div className="mt-4">
          <CustomProductForm
            ingredientId={effectiveIngredientId(creatingFor.item) as string}
            barcode={creatingFor.barcode}
            suggestion={creatingFor.suggestion}
            onCreated={(product) => {
              setResolved((prev) => ({
                ...prev,
                [creatingFor.item.id]: { kind: "product", product },
              }));
              setCreatingFor(null);
            }}
          />
        </div>
      )}

      {stock.isError && (
        <p role="alert" className="mt-4 text-sm text-red-600">
          Non sono riuscito a mettere in dispensa. Quel che hai confermato è ancora qui: riprova.
        </p>
      )}

      <button
        type="button"
        onClick={() => stock.mutate()}
        disabled={Object.keys(resolved).length === 0 || stock.isPending}
        className="mt-6 w-full rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
      >
        Metti in dispensa
      </button>
    </div>
  );
}

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cookRecipe } from "../recipes/api";
import type { PantryItem, PantryStatus, RecipeDetail } from "../../domain/types";

type Choice = { status: PantryStatus | "unchanged"; restock: boolean };

const OPTIONS: [PantryStatus | "unchanged", string][] = [
  ["unchanged", "Invariato"],
  ["low", "Quasi finito"],
  ["finished", "Finito"],
];

export function CookSheet({
  recipe,
  pantryItems,
  onDone,
}: {
  recipe: RecipeDetail;
  pantryItems: PantryItem[];
  onDone: () => void;
}) {
  // solo le voci di dispensa che appartengono a questa ricetta. La revisione opera
  // su vasetti concreti, non sull'ingrediente astratto: due vasetti di yogurt greco
  // sono due righe distinte, con due esiti distinti.
  const used = pantryItems.filter((item) =>
    recipe.ingredients.some((line) => line.ingredient_id === item.ingredient_id)
  );

  const [choices, setChoices] = useState<Record<string, Choice>>(
    Object.fromEntries(used.map((item) => [item.id, { status: "unchanged", restock: false }]))
  );

  const queryClient = useQueryClient();
  const cook = useMutation({
    mutationFn: () =>
      cookRecipe(recipe.id, {
        servings: recipe.servings ?? undefined,
        // invariato non è una transizione: non si manda
        transitions: Object.entries(choices)
          .filter(([, choice]) => choice.status !== "unchanged")
          .map(([pantryItemId, choice]) => ({
            pantry_item_id: pantryItemId,
            to_status: choice.status as PantryStatus,
            restock: choice.restock,
          })),
      }),
    onSuccess: () => {
      // cucinare cambia sia la dispensa (gli stati appena dichiarati) sia la lista
      // della spesa (il riacquisto di ciò che è finito): senza invalidare entrambe
      // l'utente torna a schermate che non mostrano quel che è appena successo, e
      // questo è esattamente il cerchio che il task deve chiudere.
      queryClient.invalidateQueries({ queryKey: ["pantry"] });
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      // anche la ricetta appena cucinata va rinfrescata: la sua disponibilità per
      // ingrediente è calcolata sulla dispensa che abbiamo appena cambiato, e
      // senza questo l'utente torna al dettaglio e legge ancora lo stato vecchio.
      queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] });
      // e l'elenco ricette, perché missing/cookable di altre ricette dipendono
      // dalla stessa dispensa.
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      onDone();
    },
  });

  function choose(itemId: string, status: PantryStatus | "unchanged") {
    setChoices({
      ...choices,
      // finito propone il riacquisto già spuntato, quasi finito no
      [itemId]: { status, restock: status === "finished" },
    });
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-neutral-500">
        Tocca solo ciò che è cambiato. Ogni confezione si dichiara da sé.
      </p>

      <ul className="divide-y divide-neutral-100">
        {used.map((item) => {
          const choice = choices[item.id];
          return (
            <li key={item.id} className="flex flex-col gap-2 py-3">
              <span className="font-medium">{item.product_name ?? item.ingredient_name}</span>
              <div className="flex gap-1">
                {OPTIONS.map(([status, label]) => (
                  <button
                    key={status}
                    type="button"
                    onClick={() => choose(item.id, status)}
                    aria-pressed={choice.status === status}
                    className={`rounded-full px-3 py-1 text-xs ${
                      choice.status === status
                        ? "bg-emerald-700 text-white"
                        : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {choice.status !== "unchanged" && (
                <label className="flex items-center gap-2 text-sm text-neutral-600">
                  <input
                    type="checkbox"
                    aria-label={`Rimetti in lista ${item.product_name ?? item.ingredient_name}`}
                    checked={choice.restock}
                    onChange={(e) =>
                      setChoices({
                        ...choices,
                        [item.id]: { ...choice, restock: e.target.checked },
                      })
                    }
                    className="size-4"
                  />
                  Rimetti in lista della spesa
                </label>
              )}
            </li>
          );
        })}
      </ul>

      {/* la mutazione segnala il proprio fallimento qui, vicino al pulsante che
          l'ha causato, non in cima a uno schermo che scorre. Le scelte fatte
          restano intatte: niente si svuota finché non arriva un successo. */}
      {cook.isError && (
        <p role="alert" className="text-sm text-red-600">
          Non sono riuscito a registrare la cottura. Le scelte qui sopra sono ancora le tue:
          riprova.
        </p>
      )}

      <button
        type="button"
        onClick={() => cook.mutate()}
        disabled={cook.isPending}
        className="rounded-lg bg-emerald-700 px-4 py-3 text-white disabled:opacity-40"
      >
        Ho cucinato
      </button>
    </div>
  );
}

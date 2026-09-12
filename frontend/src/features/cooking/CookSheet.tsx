import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cookRecipe } from "../recipes/api";
import { STATUS_LABELS, STATUS_TONE } from "../pantry/statusLabels";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { CookResult, PantryItem, PantryStatus, RecipeDetail } from "../../domain/types";

type Choice = { status: PantryStatus | "unchanged"; restock: boolean };

// Una voce non toccata non è una transizione: è il valore di partenza di ogni riga
// e la risposta alla domanda che il foglio non fa.
const UNCHANGED: Choice = { status: "unchanged", restock: false };

// Le stesse parole della dispensa, perché è lo stesso giudizio. "available" non è
// fra le scelte: cucinare non fa ricomparire niente.
const OPTIONS: [PantryStatus | "unchanged", string][] = [
  ["unchanged", "Invariato"],
  ["low", STATUS_LABELS.low],
  ["finished", STATUS_LABELS.finished],
];

function addedOn(item: PantryItem): string {
  return new Date(item.added_at).toLocaleDateString("it-IT");
}

// Tutto ciò che distingue una confezione da un'altra dello stesso ingrediente:
// prodotto, marca, nota, stato attuale e da quando è in dispensa. Serve sia scritto
// nella riga sia come nome accessibile dei controlli: senza, due sacchi di pasta
// senza codice a barre sono due righe identiche e la dichiarazione finisce su
// quello sbagliato — il vasetto vero resta "disponibile" e niente torna in lista.
function itemLabel(item: PantryItem): string {
  return [
    item.product_name ?? item.ingredient_name,
    item.product_brand,
    item.note,
    STATUS_LABELS[item.status],
    `in dispensa dal ${addedOn(item)}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function CookSheet({
  recipe,
  pantryItems,
  onDone,
}: {
  recipe: RecipeDetail;
  pantryItems: PantryItem[];
  // l'esito arriva a chi ci sta sopra, che è l'unico a essere ancora montato dopo:
  // senza argomento quando si annulla, perché non c'è nessuna cottura da riferire
  onDone: (result?: CookResult) => void;
}) {
  // solo le voci di dispensa che appartengono a questa ricetta. La revisione opera
  // su vasetti concreti, non sull'ingrediente astratto: due vasetti di yogurt greco
  // sono due righe distinte, con due esiti distinti.
  //
  // Le voci già finite restano fuori: GET /pantry le restituisce finché non vengono
  // archiviate, e una confezione già finita non ha nulla da dichiarare dopo una
  // cottura — in mezzo a cinque "pasta" finite l'unico sacco vero diventa
  // impossibile da riconoscere. Si archiviano dalla dispensa, non da qui.
  const used = pantryItems.filter(
    (item) =>
      item.status !== "finished" &&
      recipe.ingredients.some((line) => line.ingredient_id === item.ingredient_id)
  );

  // niente istantanea al mount: le righe vengono da una prop viva (la query della
  // dispensa si aggiorna anche a foglio aperto) e una voce comparsa dopo non
  // troverebbe la sua casella
  const [choices, setChoices] = useState<Record<string, Choice>>({});

  const queryClient = useQueryClient();
  const cook = useMutation({
    mutationFn: () =>
      cookRecipe(recipe.id, {
        servings: recipe.servings ?? undefined,
        // si parte da ciò che è in elenco, non da ciò che è stato cliccato: una voce
        // sparita dalla dispensa mentre il foglio era aperto farebbe fallire tutta
        // la cottura per un id che l'utente non ha più davanti e non può togliere.
        // E invariato non è una transizione: non si manda.
        transitions: used
          .map((item) => ({ item, choice: choices[item.id] ?? UNCHANGED }))
          .filter(({ choice }) => choice.status !== "unchanged")
          .map(({ item, choice }) => ({
            pantry_item_id: item.id,
            to_status: choice.status as PantryStatus,
            restock: choice.restock,
          })),
      }),
    onSuccess: (result) => {
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
      // l'esito passa di sopra: chi ha dichiarato due vasetti finiti ha diritto di
      // sapere quanto è tornato in lista, e questo foglio sta per smontarsi
      onDone(result);
    },
  });

  function choose(itemId: string, status: PantryStatus | "unchanged") {
    setChoices((current) => ({
      ...current,
      // finito propone il riacquisto già spuntato, quasi finito no
      [itemId]: { status, restock: status === "finished" },
    }));
  }

  function setRestock(itemId: string, restock: boolean) {
    setChoices((current) => ({
      ...current,
      [itemId]: { ...(current[itemId] ?? UNCHANGED), restock },
    }));
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-soft">
        Tocca solo ciò che è cambiato. Ogni confezione si dichiara da sé.
      </p>

      {/* un foglio vuoto in silenzio si legge come un guasto: dire perché è vuoto
          costa una riga. Cucinare resta possibile: la cottura si registra comunque */}
      {used.length === 0 ? (
        <p className="text-sm text-ink-soft">
          Niente di questa ricetta è in dispensa: non c'è nulla da aggiornare.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {used.map((item) => {
            const choice = choices[item.id] ?? UNCHANGED;
            const label = itemLabel(item);
            return (
              <Card as="li" key={item.id} className="flex flex-col gap-2">
                <div>
                  {/* la marca che hai comprato è più utile del nome generico */}
                  <span className="font-medium">{item.product_name ?? item.ingredient_name}</span>
                  {item.product_brand && (
                    <span className="ml-2 text-sm text-ink-faint">{item.product_brand}</span>
                  )}
                </div>
                {item.note && <p className="text-xs text-ink-soft">{item.note}</p>}
                {/* lo stato attuale dà un referente a "Invariato", e la data separa
                    il sacco di ieri da quello di stamattina */}
                <p className="text-xs text-ink-soft">
                  {STATUS_LABELS[item.status]} · in dispensa dal {addedOn(item)}
                </p>
                {/* bersagli da pollice e un gruppo con nome, come in dispensa: da
                    telefono tre pulsanti da 26px senza nome sono tre bersagli
                    mancabili e, per chi legge con lo screen reader, tre "Finito"
                    senza indicazione di quale confezione */}
                <div className="flex gap-1.5" role="group" aria-label={label}>
                  {OPTIONS.map(([status, optionLabel]) => (
                    <button
                      key={status}
                      type="button"
                      onClick={() => choose(item.id, status)}
                      aria-pressed={choice.status === status}
                      // i colori degli stati vengono dalla stessa mappa della
                      // dispensa: è lo stesso giudizio, e due schermi che se lo
                      // colorano da soli prima o poi si contraddicono. «Invariato»
                      // non è uno stato, quindi quando è scelto resta contornato e
                      // non pieno — il pieno vuol dire «qui hai dichiarato qualcosa»
                      className={`min-h-11 flex-1 rounded-full px-3 py-2 text-xs font-medium transition-colors ${
                        choice.status !== status
                          ? "bg-page text-ink-soft ring-1 ring-line ring-inset"
                          : status === "unchanged"
                            ? "bg-card text-ink ring-2 ring-ink ring-inset"
                            : STATUS_TONE[status].fill
                      }`}
                    >
                      {optionLabel}
                    </button>
                  ))}
                </div>
                {choice.status !== "unchanged" && (
                  <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">
                    <input
                      type="checkbox"
                      aria-label={`Rimetti in lista ${label}`}
                      checked={choice.restock}
                      onChange={(e) => setRestock(item.id, e.target.checked)}
                      className="size-5"
                    />
                    Rimetti in lista della spesa
                  </label>
                )}
              </Card>
            );
          })}
        </ul>
      )}

      {/* la mutazione segnala il proprio fallimento qui, vicino al pulsante che
          l'ha causato, non in cima a uno schermo che scorre. Le scelte fatte
          restano intatte: niente si svuota finché non arriva un successo. */}
      {cook.isError && (
        <Alert>
          Non sono riuscito a registrare la cottura. Le scelte qui sopra sono ancora le tue:
          riprova.
        </Alert>
      )}

      <div className="flex gap-2">
        {/* si entra qui anche per sbaglio: senza questa uscita l'unico modo di
            tornare alla ricetta è registrare una cottura che non è avvenuta */}
        <button
          type="button"
          onClick={() => onDone()}
          disabled={cook.isPending}
          className={`${buttonClasses("secondary", "block")} flex-1`}
        >
          Annulla
        </button>
        <button
          type="button"
          onClick={() => cook.mutate()}
          disabled={cook.isPending}
          className={`${buttonClasses("primary", "block")} flex-[2]`}
        >
          Ho cucinato
        </button>
      </div>
    </div>
  );
}

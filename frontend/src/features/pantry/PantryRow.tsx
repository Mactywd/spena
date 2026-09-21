import { useEffect, useState } from "react";
import { FillSlider } from "./FillSlider";
import { fillForStatus } from "./fillZones";
import { Alert } from "../../components/ui/Alert";
import { ExpiryChip } from "../../components/ui/ExpiryChip";
import { StatusChip } from "../../components/ui/StatusChip";
import type { PantryItem, RestockResult } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: la marca se c'è, l'ingrediente
 * altrimenti. Entra anche nel nome accessibile della X, perché «Togli dalla
 * dispensa» ripetuto identico su trenta righe non dice quale riga si sta togliendo. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

/** Una riga della dispensa.
 *
 * `removed` è la lapide: la riga resta dov'era, con l'annulla dentro, per i secondi
 * in cui il gesto si può disfare. Sparisce da sé quando lo schermo ricarica. Se
 * `failed` è vero mentre la lapide è a video, è l'annulla stesso che ha fallito:
 * il messaggio compare dentro la lapide (non ha più senso accanto al cursore, che
 * qui non c'è), e la lapide non scade da sola — solo un altro annulla, riuscito
 * stavolta, la può togliere.
 */
export function PantryRow({
  item,
  busy,
  removed,
  failed,
  onFill,
  onRemove,
  onUndo,
  onRestock,
  onExpiry,
}: {
  item: PantryItem;
  busy: boolean;
  removed: boolean;
  failed: boolean;
  onFill: (percent: number) => Promise<PantryItem>;
  onRemove: () => void;
  onUndo: () => void;
  onRestock: () => Promise<RestockResult>;
  onExpiry: (expiresOn: string | null) => Promise<PantryItem>;
}) {
  // la domanda vive qui e non nello schermo: riguarda questa riga, e fuori di qui
  // sarebbe un avviso in cima a una dispensa lunga, cioè fuori schermo
  const [asking, setAsking] = useState(false);
  const [restocked, setRestocked] = useState<RestockResult | null>(null);
  // mai un vicolo cieco: se il rientro in lista fallisce, la domanda torna a
  // video (non resta chiusa su un errore muto) e «Sì» è di nuovo un modo di riprovare
  const [restockFailed, setRestockFailed] = useState(false);
  // se il campo della scadenza è aperto. Stessa ragione di `asking`: riguarda
  // questa riga sola, e vive qui perché uno stato in cima allo schermo
  // aprirebbe il campo sbagliato quando due voci condividono l'ingrediente.
  const [editingExpiry, setEditingExpiry] = useState(false);

  // la riga non si smonta quando diventa una lapide (stessa chiave, stesso
  // fiber): senza questo, la domanda risposta prima dell'archiviazione resta
  // accesa in memoria e, al ritorno dall'annulla, si ripresenta da sola senza
  // nessun gesto nuovo dell'utente. Il difetto è fra due rami della stessa riga,
  // non fra due righe: si azzera qui, seguendo `removed`, in entrambe le direzioni.
  // `editingExpiry` segue la stessa regola: un campo aperto non deve riapparire
  // da sé dopo un annulla.
  useEffect(() => {
    setAsking(false);
    setRestocked(null);
    setRestockFailed(false);
    setEditingExpiry(false);
  }, [removed]);

  async function fill(percent: number) {
    setRestocked(null);
    setRestockFailed(false);
    try {
      const updated = await onFill(percent);
      // Quali stati chiedono lo dice il server, non una soglia ricopiata qui.
      // Chiede anche il giallo, e non solo lo zero: «quasi finito» è il momento in
      // cui ricomprare è ancora in tempo, mentre allo zero te ne accorgi in cucina.
      // I due stati sono scritti per esteso invece di «diverso da disponibile»:
      // se un giorno ne nascesse un quarto, questa riga deve smettere di compilare
      // e non decidere da sé che anche quello vuole la domanda.
      setAsking(updated.status === "finished" || updated.status === "low");
    } catch {
      // il guasto lo mostra già lo schermo, accanto a questa riga
      setAsking(false);
    }
  }

  async function askRestock() {
    // la domanda resta a video finché la richiesta è in volo (non si chiude
    // subito, di ottimismo): è quello che permette a `busy` di disabilitare
    // «Sì»/«No» sul serio, allo stesso modo in cui il resto del file disabilita
    // il proprio controllo durante una mutazione, invece di farlo sparire prima
    setRestockFailed(false);
    try {
      const result = await onRestock();
      setAsking(false);
      setRestocked(result);
    } catch {
      setRestocked(null);
      setRestockFailed(true);
    }
  }

  // Si scrive all'uscita dal campo, non a ogni battuta, e non è una preferenza.
  // Un `input[type="date"]` non fa scattare `change` una volta alla fine: lo fa a
  // ogni segmento toccato. Misurato in Chromium, correggere l'anno di «2026-09-28»
  // battendo «2027» produce «0002-09-28», «0020-09-28», «0202-09-28», «2027-09-28»:
  // legato al `change`, il primo di quei quattro chiudeva il campo sotto le dita e
  // salvava una data dell'anno 2, che il server giudicava scaduta. Restava solo il
  // calendario nativo, ed è la ragione per cui l'e2e non l'aveva mai visto —
  // `fill()` di Playwright scrive il valore in un colpo solo. Il campo è per questo
  // non controllato (`defaultValue`): i valori di passaggio non devono risalire da
  // nessuna parte, devono solo restare nel campo finché l'utente non ha finito.
  //
  // Il campo chiude qui e non quando la richiesta torna: la lettura successiva
  // arriva da `item` (invalidato in caso di successo), e un fallimento lo dice già
  // l'`Alert` qui sotto — non serve tenere il campo aperto per mostrarlo.
  async function commitExpiry(value: string) {
    setEditingExpiry(false);
    // uscire senza aver toccato niente non è una scrittura: aprire «+ scadenza» e
    // ripensarci manderebbe una cancellazione su una voce che data non ne ha
    if (value === (item.expires_on ?? "")) return;
    try {
      await onExpiry(value || null);
    } catch {
      // niente qui: il guasto lo mostra già l'`Alert` della riga
    }
  }

  if (removed) {
    return (
      <li className="flex flex-col gap-2 p-3" role="status">
        <div className="flex min-h-11 items-center justify-between gap-3">
          <span className="min-w-0 truncate text-ink-soft">
            <span className="font-medium text-ink">{itemLabel(item)}</span> Tolta dalla dispensa
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={onUndo}
            className="min-h-11 shrink-0 px-2 text-sm font-medium text-brand disabled:opacity-40"
          >
            Annulla
          </button>
        </div>
        {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-2.5 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* la marca che hai comprato è più utile del nome generico */}
          <span className="font-medium">{itemLabel(item)}</span>
          {/* lo spazio è scritto a mano perché `ml-2` è un margine, non del testo:
              senza, il nome accessibile della riga si legge «Total 0%Fage» */}
          {item.product_brand && (
            <>
              {" "}
              <span className="text-sm text-ink-faint">{item.product_brand}</span>
            </>
          )}
        </div>
        {/* una X, non più un link testuale. Il nome accessibile resta una frase
            intera e nomina la voce: è anche il nome con cui si comanda a voce
            questo bersaglio, e «Togli dalla dispensa» su trenta righe è ambiguo */}
        <button
          type="button"
          disabled={busy}
          onClick={onRemove}
          aria-label={`Togli ${itemLabel(item)} dalla dispensa`}
          className="-mt-1 -mr-1 flex size-11 shrink-0 items-center justify-center rounded-full text-danger disabled:opacity-40"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <FillSlider
        value={item.fill_percent ?? fillForStatus(item.status)}
        label={itemLabel(item)}
        disabled={busy}
        onCommit={fill}
      />
      <div className="flex flex-wrap items-center gap-2">
        {/* la verità sullo stato la dice il server, e questa pastiglia è l'unica cosa
            nella riga a dirla: il cursore, da solo, è un'indicazione a occhio */}
        <StatusChip status={item.status} />
        {/* la scadenza accanto allo stato, non al posto suo: due pastiglie dicono
            due fatti diversi (vedi ExpiryChip). Senza data non c'è vicolo cieco:
            resta sempre un modo di scriverla, anche per chi l'ha saltata
            all'ingresso. */}
        {editingExpiry ? (
          <div>
            <label htmlFor={`expiry-${item.id}`} className="sr-only">
              Scadenza di {itemLabel(item)}
            </label>
            <input
              id={`expiry-${item.id}`}
              type="date"
              disabled={busy}
              // il campo prende fuoco appena compare: è stato chiesto con un tocco,
              // e così l'uscita — cioè la scrittura — è a un tocco qualsiasi di
              // distanza, invece di restare aperto e muto per chi non lo tocca più
              autoFocus
              defaultValue={item.expires_on ?? ""}
              onBlur={(event) => void commitExpiry(event.target.value)}
              // Invio salva senza dover toccare altrove. Passa dal `blur`, non da una
              // seconda chiamata: la scrittura resta una strada sola.
              onKeyDown={(event) => {
                if (event.key === "Enter") event.currentTarget.blur();
              }}
            />
          </div>
        ) : item.expires_on ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => setEditingExpiry(true)}
            // stessa tecnica del «+ scadenza» qui sotto, con la misura di questo
            // contenuto: la pastiglia è alta 24px (12px di testo più `py-1`), quindi
            // bastano 10px di padding per parte a portare il riquadro a 44px, e il
            // margine negativo uguale lo ritoglie dal flusso — la riga resta alta
            // quanto lo StatusChip che le sta accanto. La sporgenza di 10px è
            // esattamente il `gap-2.5` che separa questa riga dal cursore: il
            // bersaglio cresce fin dove c'è vuoto e non si mangia quello del vicino.
            // Non è un dettaglio di eleganza: è il tocco con cui si corregge una data
            // sbagliata, cioè l'unica uscita dal vicolo cieco (spec §6).
            //
            // `flex` non è decorazione: la pastiglia è un `inline-block`, e in un
            // pulsante di blocco il suo riquadro di riga si porta dietro lo spazio
            // del discendente — 26px invece di 24, misurati, cioè un bersaglio da
            // 46px e la riga più alta di due. Da elemento flex la pastiglia è alta
            // quanto è, e la riga resta identica al pixel.
            className="-my-2.5 flex py-2.5"
          >
            <ExpiryChip expiresOn={item.expires_on} expiry={item.expiry} />
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => setEditingExpiry(true)}
            // il disegno resta minuscolo (12px, tinta smorta: su venti righe dev'essere
            // una colonnina grigia, non una fila di bottoni), il bersaglio no. Il
            // padding porta il riquadro a 44px, il margine negativo lo ritoglie dal
            // flusso: la riga della pastiglia resta alta quanto lo StatusChip (24px) e
            // la dispensa non si allunga di un pixel. La sporgenza è di 10px per parte,
            // cioè esattamente il `gap-2.5` che separa questa riga dal cursore: il
            // bersaglio cresce fin dove c'è vuoto e non si mangia quello del vicino.
            className="-my-3.5 py-3.5 text-xs font-medium text-ink-faint"
          >
            + scadenza
          </button>
        )}
      </div>
      {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}

      {asking && (
        <div className="flex items-center justify-between gap-2 rounded-card bg-page px-3 py-2">
          <span className="text-sm text-ink-soft">Lo rimetto in lista?</span>
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              onClick={askRestock}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-brand disabled:opacity-40"
            >
              Sì
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setAsking(false)}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-ink-soft disabled:opacity-40"
            >
              No
            </button>
          </span>
        </div>
      )}

      {restockFailed && <Alert>Non sono riuscito a rimettere la voce in lista. Riprova.</Alert>}

      {restocked && (
        <p role="status" className="text-sm text-ink-soft">
          {restocked.added ? "Rimesso in lista." : "Era già in lista."}
        </p>
      )}
    </li>
  );
}

import { useEffect, useId, useRef, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { buttonClasses } from "../../components/ui/buttonClasses";
import {
  IconBarcode,
  IconCalendarPlus,
  IconLink,
  IconListSearch,
  IconRefresh,
  IconReplace,
  IconScale,
  IconX,
} from "../../components/ui/icons";
import { revealAtTop } from "../../lib/revealAtTop";
import { EXPIRY_INPUT_MAX } from "../pantry/expiryLabels";
import type { FocusTarget, PanelTrigger, Resolution } from "./stockingView";
import type { ShoppingItem } from "../../domain/types";

/** Una voce di «Sistema la spesa» (spec T3 §4.3). Il nome sopra; sotto, in piccolo, a
 * cosa si è risolta — «Sfuso», o il prodotto con la marca — come una riga della
 * dispensa (dal giro: prima si riconosceva solo dal verde). A destra le tre icone
 * codice / catalogo / sfuso, o «Cambia» a voce risolta, o «Abbina» a una voce senza
 * ingrediente. Sotto, il pannello aperto per questa voce, l'avviso di S19 e la
 * scadenza. */
export function StockingRow({
  item,
  resolution,
  ingredientId,
  expiry,
  onExpiry,
  matchNotSaved,
  retryingMatch,
  onRetryMatch,
  focused,
  returnFocusTo,
  onFocusReturned,
  onOpen,
  onLoose,
  onChange,
  children,
}: {
  item: ShoppingItem;
  resolution: Resolution | undefined;
  /** L'ingrediente della voce, dalla lista o abbinato in questo schermo. */
  ingredientId: string | null;
  /** `undefined`: il campo della scadenza è chiuso. Una stringa, anche vuota: è aperto. */
  expiry: string | undefined;
  /** `""` apre il campo, una data la scrive, `undefined` lo chiude svuotandolo. */
  onExpiry: (value: string | undefined) => void;
  matchNotSaved: boolean;
  retryingMatch: boolean;
  onRetryMatch: () => void;
  /** Il pannello di questa voce è aperto: la voce va in cima (S10). */
  focused: boolean;
  returnFocusTo: FocusTarget | null;
  onFocusReturned: () => void;
  onOpen: (trigger: PanelTrigger) => void;
  onLoose: () => void;
  onChange: () => void;
  /** Il pannello aperto, sotto la riga e dentro la voce: prima stavano tutti in fondo
   * alla pagina, fuori vista (S10). */
  children?: ReactNode;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const expiryButton = useRef<HTMLButtonElement>(null);
  // la ✕ ed Esc chiudono il campo: il fuoco torna a «+ scadenza» invece di cadere sul
  // `body` insieme al campo che sparisce
  const refocusExpiry = useRef(false);
  // «+ scadenza» porta il fuoco nel campo. Non `autoFocus`: la riga rinasce a ogni
  // pannello aperto o chiuso (decisione 21, il campo resta aperto), e a ogni rinascita il
  // campo si riprendeva il fuoco — quello di «Annulla» finiva nella data di un'altra voce
  // invece che sul pulsante che aveva aperto il pannello (misurato nell'e2e). Solo il
  // tocco lo chiede, e una riga appena nata non l'ha avuto
  const expiryInput = useRef<HTMLInputElement>(null);
  const focusExpiryInput = useRef(false);
  const expiryId = useId();
  const name = item.raw_text;
  const expiryOpen = expiry !== undefined;

  // `scroll-mt-16` sulla `<li>` dice dove fermarsi: l'intestazione fissa (h-12) più un
  // respiro, come in Dispensa
  useEffect(() => {
    if (focused && ref.current) revealAtTop(ref.current);
  }, [focused]);

  // La vista cambia forma aprendo e chiudendo un pannello, e questa riga rinasce: il
  // pulsante che aveva il fuoco non c'è più. Lo schermo dice dove rimetterlo; `Button`
  // non passa `ref`, quindi lo si cerca per il `data-trigger` dello span che lo avvolge.
  // Solo se il fuoco è caduto sulla pagina: è sempre così quando il pulsante che lo
  // aveva è sparito, e una richiesta arrivata in ritardo (la rilettura dopo un
  // abbinamento) non lo toglie a chi è già andato altrove
  useEffect(() => {
    if (!returnFocusTo || !ref.current) return;
    const lost = document.activeElement === null || document.activeElement === document.body;
    if (lost) {
      ref.current.querySelector<HTMLElement>(`[data-trigger="${returnFocusTo}"] button`)?.focus();
    }
    onFocusReturned();
  }, [returnFocusTo, onFocusReturned]);

  useEffect(() => {
    if (!expiryOpen && refocusExpiry.current) {
      refocusExpiry.current = false;
      expiryButton.current?.focus();
    }
    if (expiryOpen && focusExpiryInput.current) {
      focusExpiryInput.current = false;
      expiryInput.current?.focus();
    }
  }, [expiryOpen]);

  function closeExpiry() {
    refocusExpiry.current = true;
    onExpiry(undefined);
  }

  return (
    <li ref={ref} className="scroll-mt-16 py-1">
      <div className="flex items-center gap-2">
        {/* `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
            `break-words` spezza un nome che non ci sta: a 375px accanto alle tre icone
            restano circa 170px (S16, in Lista) */}
        <div className="min-w-0 flex-1 break-words">
          <p className="font-medium">{name}</p>
          {resolution && (
            <p className="text-xs text-ink-soft">
              {resolution.kind === "loose" ? (
                "Sfuso"
              ) : (
                <>
                  <span>{resolution.product.name}</span>
                  {resolution.product.brand && <span> · {resolution.product.brand}</span>}
                </>
              )}
            </p>
          )}
        </div>
        {resolution ? (
          // «Cambia» non è più un'azione principale: un'icona, grigia (spec §4.3)
          <span data-trigger="change" className="contents">
            <Button
              variant="ghost"
              icon={IconReplace}
              label={`Cambia la scelta per ${name}`}
              onClick={onChange}
            />
          </span>
        ) : ingredientId ? (
          <IconToolbar label={`Come entra in dispensa: ${name}`}>
            <span data-trigger="scanner" className="contents">
              <Button
                variant="ghost"
                icon={IconBarcode}
                label={`Codice a barre per ${name}`}
                onClick={() => onOpen("scanner")}
              />
            </span>
            <span data-trigger="catalog" className="contents">
              <Button
                variant="ghost"
                icon={IconListSearch}
                label={`Cerca a catalogo per ${name}`}
                onClick={() => onOpen("catalog")}
              />
            </span>
            <Button
              variant="ghost"
              icon={IconScale}
              label={`Sfuso, senza marca: ${name}`}
              onClick={onLoose}
            />
          </IconToolbar>
        ) : (
          // la voce non abbinata è chiusa: una riga con «Abbina» (dal giro: il blocco
          // aperto occupava una schermata e mezza per voce). Un pulsante da solo: icona
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti. In
          // `aria-label` e non in uno `sr-only`: lo `sr-only` è posizionato, quindi a
          // blocco, e Chromium ci mette uno spazio davanti — il nome diventava «Abbina :
          // X» (misurato nell'e2e; jsdom non lo vede). `Button` con del testo non accetta
          // `label`, da cui il `<button>` a mano, come «Riprova» qui sotto
          <span data-trigger="match" className="contents">
            <button
              type="button"
              aria-label={`Abbina: ${name}`}
              onClick={() => onOpen("match")}
              className={`${buttonClasses("secondary")} shrink-0`}
            >
              <IconLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
              Abbina
            </button>
          </span>
        )}
      </div>

      {children && <div className="pt-2 pb-2">{children}</div>}

      {/* accanto alla voce, e non un muro: la voce resta sistemabile dal match locale,
          e l'abbinamento si può riprovare a scrivere (S19) */}
      {matchNotSaved && (
        <div className="flex flex-col items-start gap-2 pb-2">
          <Alert>
            Non sono riuscito a ricordare l'abbinamento in lista: la voce si sistema lo stesso,
            ma se oggi non la metti in dispensa andrà rifatto.
          </Alert>
          <button
            type="button"
            aria-disabled={retryingMatch || undefined}
            onClick={() => {
              if (!retryingMatch) onRetryMatch();
            }}
            className={`${buttonClasses("secondary")} aria-disabled:opacity-40`}
          >
            {/* un pulsante da solo: icona e testo (regola delle icone, spec §2) */}
            <IconRefresh aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
            {/* lo spazio fuori dallo `sr-only` (dal giro): dentro, il calcolo del nome
                accessibile lo perde, e «Riprova» e «ad abbinare X» si univano senza
                spazio */}
            Riprova <span className="sr-only">ad abbinare {name}</span>
          </button>
        </div>
      )}

      {/* Dietro un tocco, sempre: dieci campi vuoti sarebbero rumore permanente sullo
          schermo più denso dell'app, per chi la scadenza non la scrive mai. Resta
          raggiungibile anche a voce risolta: la data riguarda il lotto che entra, non
          come è stato scelto il prodotto */}
      {expiryOpen ? (
        <div className="flex items-end gap-1 pb-1">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {/* un'etichetta che si vede (dal giro): prima era solo per lo screen reader */}
            <label htmlFor={expiryId} className="text-xs text-ink-soft">
              Scadenza <span className="sr-only">di {name}</span>
            </label>
            <input
              ref={expiryInput}
              id={expiryId}
              type="date"
              max={EXPIRY_INPUT_MAX}
              value={expiry}
              onChange={(e) => onExpiry(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  // la data si manda con «Metti in dispensa», non c'è niente da
                  // confermare; e senza `preventDefault` l'Invio arrivava al pulsante che
                  // riprendeva il fuoco (la lezione della Consegna 1)
                  e.preventDefault();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  closeExpiry();
                }
              }}
            />
          </div>
          <Button
            variant="ghost"
            icon={IconX}
            label={`Togli la data di scadenza per ${name}`}
            onClick={closeExpiry}
          />
        </div>
      ) : (
        <button
          ref={expiryButton}
          type="button"
          onClick={() => {
            focusExpiryInput.current = true;
            onExpiry("");
          }}
          className="flex min-h-11 items-center gap-1 text-xs font-medium text-ink-faint"
        >
          <IconCalendarPlus aria-hidden="true" className="size-4" stroke={1.8} />
          {/* lo spazio fuori dallo `sr-only`, come sopra */}
          + scadenza <span className="sr-only">per {name}</span>
        </button>
      )}
    </li>
  );
}

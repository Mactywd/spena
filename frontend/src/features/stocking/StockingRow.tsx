import { useEffect, useRef, type ReactNode } from "react";
import { ExpiryField } from "./ExpiryField";
import { ResolutionNote } from "./ResolutionNote";
import { useReturnFocus } from "./useReturnFocus";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconLink,
  IconListSearch,
  IconRefresh,
  IconReplace,
  IconScale,
} from "../../components/ui/icons";
import { revealAtTop } from "../../lib/revealAtTop";
import { capitalizeFirst } from "../../lib/text";
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
  after,
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
  /** In fondo alla voce, dopo la sua scadenza: le confezioni in più e «+ un'altra
   * confezione» (S3 §10.2). */
  after?: ReactNode;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const name = item.raw_text;

  // `scroll-mt-16` sulla `<li>` dice dove fermarsi: l'intestazione fissa (h-12) più un
  // respiro, come in Dispensa
  useEffect(() => {
    if (focused && ref.current) revealAtTop(ref.current);
  }, [focused]);

  useReturnFocus(ref, returnFocusTo, onFocusReturned);

  return (
    <li ref={ref} className="scroll-mt-16 py-1">
      <div className="flex items-center gap-2">
        {/* `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
            `break-words` spezza un nome che non ci sta: a 375px accanto alle tre icone
            restano circa 170px (S16, in Lista) */}
        <div className="min-w-0 flex-1 break-words">
          {/* la maiuscola solo a video, come in Lista (Mattia, 2026-10-13); `name` resta
              com'è scritto per i nomi accessibili qui sotto, che lo mettono in una frase */}
          <p className="font-medium">{capitalizeFirst(name)}</p>
          {resolution && <ResolutionNote resolution={resolution} />}
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
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti, con
          // `accessibleName` (Consegna 6a). Non uno `sr-only`: è posizionato, quindi a
          // blocco, e Chromium ci metteva uno spazio davanti — il nome diventava «Abbina :
          // X» (misurato nell'e2e; jsdom non lo vede)
          <span data-trigger="match" className="contents">
            <Button
              icon={IconLink}
              accessibleName={`Abbina: ${name}`}
              onClick={() => onOpen("match")}
              className="shrink-0"
            >
              Abbina
            </Button>
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
          {/* un pulsante da solo: icona e testo (regola delle icone, spec §2). Il nome
              dice cosa riprova, con `accessibleName` (Consegna 6a); `busy` mentre la
              scrittura è in volo, e il fuoco resta */}
          <Button
            icon={IconRefresh}
            accessibleName={`Riprova ad abbinare ${name}`}
            busy={retryingMatch}
            onClick={onRetryMatch}
          >
            Riprova
          </Button>
        </div>
      )}

      {/* resta raggiungibile anche a voce risolta: la data riguarda il lotto che entra,
          non come è stato scelto il prodotto */}
      <ExpiryField name={name} value={expiry} onChange={onExpiry} />
      {after}
    </li>
  );
}

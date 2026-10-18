import { useRef, type ReactNode } from "react";
import { ExpiryField } from "./ExpiryField";
import { ResolutionNote } from "./ResolutionNote";
import { useReturnFocus } from "./useReturnFocus";
import type { FocusTarget, Resolution } from "./stockingView";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconListSearch,
  IconReplace,
  IconScale,
  IconX,
} from "../../components/ui/icons";

/** Una confezione in più di una voce di «Sistema la spesa» (S3 §10.2, decisa da Mattia
 * il 2026-10-07): da «prosciutto cotto» due vaschette con due scadenze, da «yogurt» una
 * alla fragola e una alla pesca. Sta sotto la voce, rientrata, con le stesse tre strade,
 * la sua «+ scadenza» e il suo pannello; è dello stesso ingrediente della voce, che è
 * quello che la guardia dello scanner e il filtro del catalogo confrontano. I nomi per
 * chi ascolta dicono quale confezione («Codice a barre per mele, confezione 2»): la prima
 * è la riga della voce, coi nomi di sempre. Le sue icone si ritrovano per
 * `data-package-trigger`, non per `data-trigger`: sta dentro la riga della voce, e le
 * due ricerche del fuoco non devono trovarsi a vicenda. */
export function PackageRow({
  name,
  index,
  resolution,
  expiry,
  onExpiry,
  returnFocusTo,
  onFocusReturned,
  onOpen,
  onLoose,
  onChange,
  onRemove,
  children,
}: {
  /** Il testo della voce. */
  name: string;
  /** Il numero della confezione, dal 2: la prima è la voce. */
  index: number;
  resolution: Resolution | undefined;
  expiry: string | undefined;
  onExpiry: (value: string | undefined) => void;
  returnFocusTo: FocusTarget | null;
  onFocusReturned: () => void;
  onOpen: (trigger: "scanner" | "catalog") => void;
  onLoose: () => void;
  onChange: () => void;
  onRemove: () => void;
  /** Il pannello aperto per questa confezione. */
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const which = `${name}, confezione ${index}`;
  useReturnFocus(ref, returnFocusTo, onFocusReturned, "data-package-trigger");

  return (
    <div ref={ref} className="border-t border-line pt-1">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1 break-words">
          <p className="text-sm font-medium">Confezione {index}</p>
          {resolution && <ResolutionNote resolution={resolution} />}
        </div>
        {resolution ? (
          <span data-package-trigger="change" className="contents">
            <Button
              variant="ghost"
              icon={IconReplace}
              label={`Cambia la scelta per ${which}`}
              onClick={onChange}
            />
          </span>
        ) : (
          <IconToolbar label={`Come entra in dispensa: ${which}`}>
            <span data-package-trigger="scanner" className="contents">
              <Button
                variant="ghost"
                icon={IconBarcode}
                label={`Codice a barre per ${which}`}
                onClick={() => onOpen("scanner")}
              />
            </span>
            <span data-package-trigger="catalog" className="contents">
              <Button
                variant="ghost"
                icon={IconListSearch}
                label={`Cerca a catalogo per ${which}`}
                onClick={() => onOpen("catalog")}
              />
            </span>
            <Button
              variant="ghost"
              icon={IconScale}
              label={`Sfuso, senza marca: ${which}`}
              onClick={onLoose}
            />
          </IconToolbar>
        )}
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli la confezione ${index} di ${name}`}
          onClick={onRemove}
        />
      </div>

      {children && <div className="pt-2 pb-2">{children}</div>}

      <ExpiryField name={which} value={expiry} onChange={onExpiry} />
    </div>
  );
}

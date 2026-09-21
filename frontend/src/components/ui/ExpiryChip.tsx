import { EXPIRY_TONE, formatExpiry } from "../../features/pantry/expiryLabels";
import type { ExpiryState } from "../../domain/types";

/** La scadenza accanto allo stato, non al posto suo: due pastiglie dicono due fatti
 * diversi. Senza verdetto la data resta leggibile in tinta neutra — è
 * un'informazione, non un allarme, finché il server non dice altro. */
export function ExpiryChip({
  expiresOn,
  expiry,
}: {
  expiresOn: string;
  expiry: ExpiryState | null;
}) {
  const tono = expiry ? EXPIRY_TONE[expiry] : "bg-page text-ink-soft";
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${tono}`}>
      {formatExpiry(expiresOn, expiry)}
    </span>
  );
}

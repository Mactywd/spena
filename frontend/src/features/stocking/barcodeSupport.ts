/**
 * La lettura nativa esiste su Android Chrome; altrove si usa zxing in WebAssembly.
 * In entrambi i casi serve HTTPS, anche in sviluppo.
 *
 * Vive in un file proprio, separato da BarcodeScanner.tsx: `react-refresh/only-
 * export-components` vieta di esportare una funzione non-componente insieme a un
 * componente dallo stesso file, perché spezza il Fast Refresh. Non è una
 * questione di versione, è la regola che vieta di farlo in qualunque versione.
 *
 * Nessuno la consuma ancora: è richiesta dall'interfaccia del brief e resta il
 * punto in cui rispondere il giorno in cui una piattaforma non avrà nessuna
 * delle due strade (il wrapper Capacitor, dove la fotocamera è un plugin). Il
 * pulsante del codice a barre non si nasconde su questa risposta: nasconderlo
 * chiuderebbe quella strada, e il campo manuale vive dentro quel pannello.
 */
export function isBarcodeScanningSupported(): boolean {
  return true; // zxing è la riserva universale, quindi la risposta è sempre sì
}

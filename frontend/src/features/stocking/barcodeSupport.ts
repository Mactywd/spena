/**
 * La lettura nativa esiste su Android Chrome; altrove si usa zxing in WebAssembly.
 * In entrambi i casi serve HTTPS, anche in sviluppo.
 *
 * Vive in un file proprio, separato da BarcodeScanner.tsx: `react-refresh/only-
 * export-components` vieta di esportare una funzione non-componente insieme a un
 * componente dallo stesso file, perché spezza il Fast Refresh. Non è una
 * questione di versione, è la regola che vieta di farlo in qualunque versione.
 */
export function isBarcodeScanningSupported(): boolean {
  return true; // zxing è la riserva universale, quindi la risposta è sempre sì
}

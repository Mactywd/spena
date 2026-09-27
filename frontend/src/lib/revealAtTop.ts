// Porta l'inizio di un elemento in cima alla vista. Quanto sotto l'intestazione
// fissa si fermi non si decide qui: lo dice lo `scroll-margin-top` dell'elemento
// (una classe `scroll-mt-*`), che resta accanto al markup e segue l'header se un
// giorno cambia altezza, invece di un numero di pixel scritto in JavaScript.
//
// Chi ha chiesto al sistema meno movimento riceve il salto secco. `matchMedia` può
// mancare (jsdom, webview vecchie): allora si anima, che è il comportamento di tutti.
export function revealAtTop(element: HTMLElement): void {
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  element.scrollIntoView({ block: "start", behavior: reduceMotion ? "auto" : "smooth" });
}

import "@testing-library/jest-dom/vitest";

// jsdom non ha layout e non implementa `scrollIntoView`: senza questo, ogni test che
// apre il foglio della cottura esploderebbe su un metodo che in un browser c'è sempre.
// Un no-op e non un finto scorrimento: cosa si porta in vista lo controllano i test
// che ci mettono una spia sopra, dove arriva lo vede solo un browser vero.
//
// Il tipo scritto a mano perché questo file sta nel progetto `tsconfig.node.json`,
// senza la libreria DOM: aggiungerla lì per una riga la darebbe anche a Playwright.
type ElementGlobal = { Element?: { prototype: { scrollIntoView?: () => void } } };
const elementPrototype = (globalThis as ElementGlobal).Element?.prototype;
if (elementPrototype && !elementPrototype.scrollIntoView) {
  elementPrototype.scrollIntoView = function scrollIntoView() {};
}

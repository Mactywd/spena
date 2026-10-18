import { configure } from "@testing-library/react";

// Le attese di Testing Library (`findBy…`, `waitFor`) arrivano a 4 s invece di 1: sotto
// carico — l'e2e che gira accanto — le schermate con più letture finte cadevano a caso,
// ogni volta su un'asserzione diversa (src/test/waits.test.ts).
//
// Sta qui e non in vitest.setup.ts perché quel file è nel progetto `tsconfig.node.json`,
// senza la libreria DOM: importarci Testing Library portava i tipi DOM a Playwright e
// faceva cadere `npm run typecheck` su e2e/*.spec.ts. Questo è nel progetto dell'app.
configure({ asyncUtilTimeout: 4000 });

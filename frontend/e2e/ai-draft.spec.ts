import { expect, test } from "@playwright/test";
import type { RecipeDraft } from "../src/domain/types.ts";

/**
 * La riga «da creare salvando» della bozza AI (`/ricette/nuova-ai`), a 375px.
 *
 * È la riga di un ingrediente che il modello propone e l'anagrafica non ha: porta il nome,
 * la sua ✕, la nota «da creare salvando», il reparto da correggere, la quantità e il
 * ruolo. Il nome viene dalla fonte, e può essere lungo. jsdom non calcola dove finisce
 * una riga: lo misura solo un browser.
 *
 * IL LIMITE DI QUESTO TEST, detto chiaro: la bozza la scrive il modello, che qui non si
 * chiama, quindi la risposta di `POST /recipes/ai-draft` la costruisce il test con
 * `page.route`. È un test che si costruisce l'oggetto da sé — la prima lezione di
 * CLAUDE.md — e non prova niente di quel che il backend manda davvero: né che una riga
 * così arrivi, né con che campi (il `satisfies` tiene lo stub almeno nella forma del
 * tipo del frontend). Vale per una cosa sola, il layout della riga a 375px, e lo schermo,
 * il componente e il CSS sono quelli veri. Non scrive niente: il salvataggio non si tocca.
 *
 * Fino a R10 questa prova fissava un difetto (pagina larga 562px, il nome in colonna,
 * alto 7 righe), perché la nota ripeteva il nome accanto a lui in uno `span` che non si
 * stringeva. `RecipeForm` mette la nota su una riga sua e senza il nome: le asserzioni
 * in fondo dicono com'è giusto.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

// Un nome da catalogo vero, di quelli che la fonte scrive per esteso
const NOME_LUNGO = "Guanciale di maiale stagionato al pepe nero dei Monti Lepini";

test.use({ viewport: { width: 375, height: 812 } });

test("a 375px la riga «da creare salvando» con un nome lungo sta nello schermo", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  let bozzeServite = 0;
  await page.route("**/api/v1/recipes/ai-draft", (route) => {
    bozzeServite += 1;
    return route.fulfill({
      json: {
        title: "Gricia",
        description: null,
        instructions: "Rosola il guanciale, manteca la pasta.",
        servings: 2,
        cost: null,
        ingredients: [
          {
            raw_name: NOME_LUNGO,
            role: "primary",
            quantity_text: "150 g",
            ingredient_id: null,
            matched_name: null,
            confident: false,
            proposed_category: "carne",
          },
        ],
      } satisfies RecipeDraft,
    });
  });

  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Cosa vuoi cucinare").fill("una gricia");
  await page.getByRole("button", { name: "Proponi", exact: true }).click();

  // la riga si trova dalla sua ✕, che porta il nome nel nome accessibile
  const togli = page.getByRole("button", { name: `Togli ${NOME_LUNGO}` });
  await expect(togli).toBeVisible();
  const riga = page.getByRole("listitem").filter({ has: togli });
  const nome = riga.getByText(NOME_LUNGO, { exact: true });
  // la nota non ripete il nome: sta su una riga sua, sotto
  await expect(riga.getByText(/da creare salvando/)).toBeVisible();
  await expect(riga.getByText("Non è in anagrafica: lo creo io salvando.")).toBeVisible();
  await expect(page.getByLabel(`Categoria per «${NOME_LUNGO}»`)).toHaveValue("carne");
  await expect(page.getByLabel(`Quantità per ${NOME_LUNGO}`)).toHaveValue("150 g");
  // la risposta l'ha data lo stub, non il modello: nessuna chiamata a OpenRouter
  expect(bozzeServite).toBe(1);

  await page.screenshot({ path: test.info().outputPath("bozza-375.png"), fullPage: true });

  // la pagina non scorre di lato
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "la bozza scorre di lato").toBeLessThanOrEqual(clientWidth);

  // e il nome sta al più su due righe, non in una colonna di una parola per riga. `el` è
  // `any` (tsconfig.node.json non ha la libreria DOM), e la finestra dell'elemento dà
  // `getComputedStyle` senza un globale.
  const forma = await nome.evaluate((el) => ({
    altezza: el.getBoundingClientRect().height as number,
    interlinea: parseFloat(el.ownerDocument.defaultView.getComputedStyle(el).lineHeight),
  }));
  test.info().annotations.push({
    type: "misura",
    description: `pagina ${scrollWidth}px su ${clientWidth}; nome alto ${forma.altezza}px, interlinea ${forma.interlinea}px`,
  });
  expect(forma.altezza, "il nome va a capo a ogni parola").toBeLessThanOrEqual(
    2 * forma.interlinea
  );
});

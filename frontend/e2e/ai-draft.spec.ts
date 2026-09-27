import { expect, test } from "@playwright/test";
import type { RecipeDraft } from "../src/domain/types.ts";

/**
 * La riga «da creare salvando» della bozza AI (`/ricette/nuova-ai`), a 375px.
 *
 * È la riga di un ingrediente che il modello propone e l'anagrafica non ha: porta la
 * casella per escluderla, la nota «da creare salvando», il reparto da correggere e la
 * quantità. Il nome viene dalla fonte, e oggi un nome lungo sta due volte sulla riga —
 * nel testo della casella e dentro la nota, che non si stringe (`shrink-0`) — in una riga
 * `justify-between`. jsdom non calcola dove finisce una riga: lo misura solo un browser.
 *
 * IL LIMITE DI QUESTO TEST, detto chiaro: la bozza la scrive il modello, che qui non si
 * chiama, quindi la risposta di `POST /recipes/ai-draft` la costruisce il test con
 * `page.route`. È un test che si costruisce l'oggetto da sé — la prima lezione di
 * CLAUDE.md — e non prova niente di quel che il backend manda davvero: né che una riga
 * così arrivi, né con che campi (il `satisfies` tiene lo stub almeno nella forma del
 * tipo del frontend). Vale per una cosa sola, il layout della riga a 375px, e lo schermo,
 * il componente e il CSS sono quelli veri. Non scrive niente: il salvataggio non si tocca.
 *
 * DIFETTO NOTO, fissato in positivo. Misurato il 2026-09-28: con questo nome (60
 * caratteri) la pagina a 375px diventa larga 562px, e il nome nella casella resta una
 * colonna di una parola per riga: alto 140px, cioè 7 righe da 20px. Le asserzioni in fondo dicono com'è oggi, non com'è
 * giusto: vanno rovesciate quando la riga si sistema (R10, `RecipeForm`), e il test
 * fallirà da solo per ricordarlo il giorno in cui la riga cambia.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

// Un nome da catalogo vero, di quelli che la fonte scrive per esteso
const NOME_LUNGO = "Guanciale di maiale stagionato al pepe nero dei Monti Lepini";

test.use({ viewport: { width: 375, height: 812 } });

test("a 375px la riga «da creare salvando» con un nome lungo: com'è oggi, difetto compreso", async ({
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

  // la riga c'è, com'è fatta: inclusa, con la sua nota, il reparto e la quantità
  const includi = page.getByRole("checkbox", { name: `Includi ${NOME_LUNGO}` });
  await expect(includi).toBeChecked();
  const etichetta = page.locator("label").filter({ has: includi });
  const nome = etichetta.getByText(NOME_LUNGO, { exact: true });
  // la nota si trova dal suo posto nella riga — l'elemento subito dopo l'etichetta della
  // casella — e non dalla frase esatta: chi sistema la riga può togliere il nome ripetuto
  const nota = etichetta.locator("xpath=following-sibling::*[1]");
  await expect(nota).toContainText("da creare salvando");
  await expect(page.getByText("Non è in anagrafica: lo creo io salvando.")).toBeVisible();
  await expect(page.getByLabel(`Categoria per «${NOME_LUNGO}»`)).toHaveValue("carne");
  await expect(page.getByLabel(`Quantità per ${NOME_LUNGO}`)).toHaveValue("150 g");
  // la risposta l'ha data lo stub, non il modello: nessuna chiamata a OpenRouter
  expect(bozzeServite).toBe(1);

  await page.screenshot({ path: test.info().outputPath("bozza-375.png"), fullPage: true });

  // Difetto noto, da rovesciare quando la riga è sistemata (R10, RecipeForm): la pagina
  // scorre di lato. Rovesciato, diventa `toBeLessThanOrEqual(clientWidth)`.
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "difetto noto: la bozza scorre di lato").toBeGreaterThan(clientWidth);

  // Difetto noto, da rovesciare quando la riga è sistemata (R10, RecipeForm): il nome
  // nella casella è schiacciato in una colonna di una parola per riga. Si misura perché
  // la correzione deve sistemare anche questo, non solo tagliare la nota: rovesciato, il
  // nome sta al più su due righe. `el` è `any` (tsconfig.node.json non ha la libreria
  // DOM), e la finestra dell'elemento dà `getComputedStyle` senza un globale.
  const forma = await nome.evaluate((el) => ({
    altezza: el.getBoundingClientRect().height as number,
    interlinea: parseFloat(el.ownerDocument.defaultView.getComputedStyle(el).lineHeight),
  }));
  test.info().annotations.push({
    type: "misura",
    description: `pagina ${scrollWidth}px su ${clientWidth}; nome alto ${forma.altezza}px, interlinea ${forma.interlinea}px`,
  });
  expect(
    forma.altezza,
    "difetto noto: il nome nella casella va a capo a ogni parola"
  ).toBeGreaterThan(2 * forma.interlinea);
});

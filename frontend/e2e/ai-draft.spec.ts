import { expect, test } from "@playwright/test";

/**
 * La riga «da creare salvando» della bozza AI (`/ricette/nuova-ai`), a 375px.
 *
 * È la riga di un ingrediente che il modello propone e l'anagrafica non ha: porta la
 * casella per escluderla, la nota «…: da creare salvando», il reparto da correggere e la
 * quantità. Il nome viene dalla fonte, e un nome lungo sta due volte sulla riga — nel
 * testo della casella e dentro la nota, che non si stringe (`shrink-0`) — in una riga
 * `justify-between`. jsdom non calcola dove finisce una riga: lo misura solo un browser.
 *
 * IL LIMITE DI QUESTO TEST, detto chiaro: la bozza la scrive il modello, che qui non si
 * chiama, quindi la risposta di `POST /recipes/ai-draft` la costruisce il test con
 * `page.route`. È un test che si costruisce l'oggetto da sé — la prima lezione di
 * CLAUDE.md — e non prova niente di quel che il backend manda davvero: né che una riga
 * così arrivi, né con che campi. Vale per una cosa sola, il layout della riga a 375px,
 * e lo schermo, il componente e il CSS sono quelli veri. Non scrive niente: il
 * salvataggio non si tocca.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

// Un nome da catalogo vero, di quelli che la fonte scrive per esteso
const NOME_LUNGO = "Guanciale di maiale stagionato al pepe nero dei Monti Lepini";

test.use({ viewport: { width: 375, height: 812 } });

test("a 375px la riga «da creare salvando» con un nome lungo sta nello schermo", async ({
  page,
}) => {
  // DIFETTO APERTO, misurato il 2026-09-28 sullo stack e2e: con questo nome (60
  // caratteri) la pagina a 375px diventa larga 562px. La nota «…: da creare salvando»
  // sta in uno `span` `shrink-0` della riga `justify-between` di `AiDraftScreen.tsx`,
  // quindi non va a capo e non si stringe: occupa il nome intero più la coda, spinge la
  // pagina di lato, e il testo della casella resta una colonna di una parola per riga.
  // Il test asserisce la cosa giusta e resta rosso di proposito: `test.fail()` lo fa
  // contare come atteso finché la riga non si sistema — e fallirà, avvisando, il giorno
  // in cui passa. Come sistemarla è una scelta di disegno (dove va la nota, se ripetere
  // il nome), e non l'ha fatta questo test: vedi Parte IX, c in docs/prossimi-passi.md.
  test.fail();

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
      },
    });
  });

  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Cosa vuoi cucinare").fill("una gricia");
  await page.getByRole("button", { name: "Proponi", exact: true }).click();

  // la riga c'è, com'è fatta: inclusa, con la sua nota, il reparto e la quantità
  const includi = page.getByRole("checkbox", { name: `Includi ${NOME_LUNGO}` });
  await expect(includi).toBeChecked();
  const nota = page.getByText(`${NOME_LUNGO}: da creare salvando`, { exact: true });
  await expect(nota).toBeVisible();
  await expect(page.getByText("Non è in anagrafica: lo creo io salvando.")).toBeVisible();
  await expect(page.getByLabel(`Categoria per «${NOME_LUNGO}»`)).toHaveValue("carne");
  await expect(page.getByLabel(`Quantità per ${NOME_LUNGO}`)).toHaveValue("150 g");
  // la risposta l'ha data lo stub, non il modello: nessuna chiamata a OpenRouter
  expect(bozzeServite).toBe(1);

  await page.screenshot({ path: test.info().outputPath("bozza-375.png"), fullPage: true });

  // la pagina non scorre di lato, e la nota e la casella stanno intere nello schermo
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "la bozza scorre di lato").toBeLessThanOrEqual(clientWidth);
  await expect(nota).toBeInViewport({ ratio: 1 });
  await expect(includi).toBeInViewport({ ratio: 1 });
});

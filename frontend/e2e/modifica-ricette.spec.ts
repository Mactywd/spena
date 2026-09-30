import { expect, test, type Page } from "@playwright/test";

/**
 * R10 nel browser vero (spec §8.6): una ricetta si modifica togliendo l'unico
 * ingrediente che manca, e diventa cucinabile; si elimina, si annulla, torna. Tutto
 * a 375×812, il telefono su cui il difetto si è visto: si arriva al dettaglio scorsi
 * in fondo, e l'esito — dal T3 Consegna 4 l'avviso unico, non più
 * la lapide in cima al ricettario (R10 §6.1) — deve farsi vedere, sopra la barra delle
 * schede. E il modulo di modifica a
 * 375 px non scorre di lato: `scrollWidth` lo calcola il browser dal CSS che
 * Tailwind ha costruito, jsdom non lo vede.
 *
 * La ricetta e la voce di dispensa si creano con `page.request`, che condivide i
 * cookie della pagina; il titolo porta l'ora, perché il ricettario vive quanto lo
 * stack. In fondo la voce si toglie e la ricetta si elimina — non esiste una
 * cancellazione vera, ed è il punto di R10 — dentro un `finally`, così un'asserzione
 * fallita a metà non lascia la dispensa sporca per le prove dopo.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("una ricetta si modifica e diventa cucinabile, si elimina e torna; a 375px il modulo non scorre di lato", async ({
  page,
}) => {
  // Il difetto è al telefono (misurato a 375×812): il resto del flusso corre qui
  // sotto, così «Elimina» finisce in fondo al dettaglio quanto ci finisce davvero.
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata e2e ${Date.now()}`;
  // il procedimento è lungo apposta: il dettaglio deve superare gli 812px della
  // finestra, o non c'è niente da scorrere e il difetto non si misura
  const procedimentoLungo = Array.from(
    { length: 20 },
    (_, i) => `${i + 1}. Taglia, condisci e mescola con calma.`
  ).join("\n");
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: procedimentoLungo, servings: 2, source: "manual",
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "1 fetta" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const { id: ricettaId } = (await creata.json()) as { id: string };
  let voceId: string | undefined;

  try {
    const inDispensa = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: cetriolo.id, status: "available" },
    });
    expect(inDispensa.ok()).toBe(true);
    voceId = (await inDispensa.json()).id as string;

    // manca l'anguria, e solo lei
    await page.goto(`/ricette/${ricettaId}`);
    await expect(page.getByRole("heading", { name: titolo })).toBeVisible();
    await expect(page.getByRole("img", { name: "manca", exact: true })).toHaveCount(1);

    // la modifica: via l'anguria, e la ricetta diventa cucinabile
    await page.getByRole("link", { name: "Modifica" }).click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}/modifica$`));
    await page.getByRole("button", { name: "Togli anguria" }).click();
    await page.getByRole("button", { name: "Salva le modifiche" }).click();

    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}$`));
    await expect(page.getByRole("status").filter({ hasText: "Salvata." })).toBeVisible();
    await expect(page.getByRole("img", { name: "manca", exact: true })).toHaveCount(0);
    const dettaglio = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
      cookable: boolean;
    };
    expect(dettaglio.cookable).toBe(true);

    // Si torna al ricettario e si rientra nel dettaglio navigando in-app — non con un
    // `page.goto` — così la lista arriva già in cache quando «Elimina» ci fa tornare:
    // è quel che succede davvero navigando con l'app, ed è la condizione sotto cui il
    // difetto si misura (senza cache calda la lista riparte da un "Cerco…" corto, che
    // azzera da solo lo scorrimento, e il difetto non si vede).
    await page.getByRole("link", { name: "Ricette" }).first().click();
    await page.getByLabel("Cerca nel ricettario").fill(titolo);
    await page.getByRole("link", { name: new RegExp(titolo) }).click();
    await expect(page.getByRole("heading", { name: titolo })).toBeVisible();

    // eliminare, annullare, tornare — la lapide del ricettario nasceva sotto l'intestazione
    // fissa (misurato: la sua `getBoundingClientRect().top` a circa −7); l'avviso unico che
    // l'ha sostituita (T3 Consegna 4) è fisso in basso, e deve stare sopra la barra delle
    // schede, a video, da dovunque si arrivi.
    // «Elimina» sta in alto, accanto al titolo (T3 Consegna 5): si scorre comunque in
    // fondo al dettaglio, perché è lì che si è dopo aver letto la ricetta, e l'avviso
    // dell'eliminazione deve farsi vedere lo stesso
    await page.mouse.wheel(0, 4000);
    await expect.poll(() => page.evaluate<number>("window.scrollY")).toBeGreaterThan(0);
    const eliminaBtn = page.getByRole("button", { name: "Elimina", exact: true });

    await eliminaBtn.click();
    await expect(page).toHaveURL(/\/ricette$/);
    const avviso = page.getByRole("status").filter({ hasText: `Eliminata: ${titolo}` });
    await expect(avviso).toBeVisible();
    await expect(avviso).toBeInViewport();
    const schede = (await page.getByRole("navigation").boundingBox())!;
    const boxAvviso = (await avviso.boundingBox())!;
    expect(
      boxAvviso.y + boxAvviso.height,
      "l'avviso finisce sotto la barra delle schede"
    ).toBeLessThanOrEqual(schede.y);
    await avviso.getByRole("button", { name: "Annulla" }).click();
    await expect(avviso).toHaveCount(0);
    await page.getByLabel("Cerca nel ricettario").fill(titolo);
    await expect(page.getByRole("link", { name: new RegExp(titolo) })).toBeVisible();

    // il modulo di modifica: la finestra è già a 375px da inizio prova
    await page.goto(`/ricette/${ricettaId}/modifica`);
    await expect(page.getByRole("button", { name: "Salva le modifiche" })).toBeVisible();
    // il ruolo non scelto è un bottone che si vede: fondo della scheda e contorno, non il
    // fondo della pagina su cui sta (--color-card: #ffffff); e un bersaglio da pollice
    const secondario = page
      .getByRole("group", { name: "Ruolo di cetriolo" })
      .getByRole("button", { name: "secondario" });
    await expect(secondario).toHaveAttribute("aria-pressed", "false");
    await expect(secondario).toHaveCSS("background-color", "rgb(255, 255, 255)");
    await expect(secondario).not.toHaveCSS("box-shadow", "none");
    expect((await secondario.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await page.screenshot({ path: test.info().outputPath("modifica-375.png"), fullPage: true });
    await nonScorreDiLato(page, "il modulo di modifica");
  } finally {
    if (voceId) await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
    await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { archived: true } });
  }
});

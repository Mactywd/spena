import { expect, test, type Page } from "@playwright/test";

/**
 * Gli utensili dal ☰ nel browser vero, a 375×812: si aggiungono, si correggono, si tolgono
 * e tornano con «Annulla», e restano dopo un ricaricamento. Gli utensili della prova si
 * tolgono nel `finally` con `page.request`, che condivide i cookie della pagina.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const NOMI = ["frusta elettrica", "padella antiaderente"];

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

function riga(page: Page, nome: string) {
  return page.getByRole("listitem").filter({ hasText: nome });
}

async function aggiungi(page: Page, nome: string, nota?: string) {
  await page.getByLabel("Nuovo utensile", { exact: true }).fill(nome);
  if (nota) await page.getByLabel("Nota del nuovo utensile", { exact: true }).fill(nota);
  await page.getByRole("button", { name: "Aggiungi", exact: true }).click();
  await expect(riga(page, nome)).toBeVisible();
}

test("gli utensili dal ☰: si aggiungono, si correggono, si tolgono e tornano con «Annulla», e restano dopo un ricaricamento", async ({
  page,
}) => {
  await entra(page);
  try {
    await page.getByRole("button", { name: "Apri il menu" }).click();
    await page.getByRole("link", { name: "Utensili" }).click();
    await expect(page).toHaveURL(/\/utensili$/);
    await expect(page.getByRole("heading", { name: "Utensili" })).toBeVisible();

    const esistenti = await page.request.get("/api/v1/utensils");
    expect(esistenti.ok()).toBe(true);
    if (((await esistenti.json()) as unknown[]).length === 0) {
      await expect(
        page.getByText("Scrivi gli strumenti che hai in cucina: le ricette scritte dall'AI useranno solo quelli")
      ).toBeVisible();
    } else {
      console.log("elenco non vuoto: salto la prova dello stato vuoto (stack riusato)");
    }

    await aggiungi(page, "frusta elettrica");
    await aggiungi(page, "padella antiaderente", "da 24 cm");
    const elementi = await page.getByRole("listitem").allTextContents();
    const iFrusta = elementi.findIndex((t) => t.includes("frusta elettrica"));
    const iPadella = elementi.findIndex((t) => t.includes("padella antiaderente"));
    expect(iFrusta).toBeGreaterThanOrEqual(0);
    expect(iFrusta).toBeLessThan(iPadella);
    await expect(riga(page, "padella antiaderente")).toContainText("da 24 cm");

    await page.getByRole("button", { name: "Correggi «padella antiaderente»" }).click();
    // con la correzione aperta il nome sta in un campo, non nel testo della riga: si cerca la riga dal campo
    const modifica = page.getByRole("listitem").filter({ has: page.getByLabel("Nome", { exact: true }) });
    await modifica.getByLabel("Nota", { exact: true }).fill("da 28 cm");
    await modifica.getByRole("button", { name: "Salva", exact: true }).click();
    await expect(riga(page, "padella antiaderente")).toContainText("da 28 cm");
    await page.reload();
    await expect(riga(page, "padella antiaderente")).toContainText("da 28 cm");

    await page.getByRole("button", { name: "Togli «frusta elettrica»" }).click();
    await expect(riga(page, "frusta elettrica")).toHaveCount(0);
    await expect(page.getByText("Tolto «frusta elettrica».")).toBeVisible();
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
    await expect(riga(page, "frusta elettrica")).toBeVisible();

    await nonScorreDiLato(page, "gli utensili");
  } finally {
    const elenco = await page.request.get("/api/v1/utensils");
    if (elenco.ok()) {
      for (const u of (await elenco.json()) as { id: string; name: string }[]) {
        if (!NOMI.includes(u.name)) continue;
        const tolto = await page.request.delete(`/api/v1/utensils/${u.id}`);
        expect.soft(tolto.ok(), `pulizia: l'utensile ${u.id} non si è tolto`).toBe(true);
      }
    }
  }
});

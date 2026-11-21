import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { giornoDiRoma } from "./giornoDiRoma.ts";

/**
 * La chat del piatto nel browser vero, a 375×812.
 *
 * Lo stack e2e non ha la chiave API di Claude: la chat vera risponde 503, ed è proprio il caso
 * della prima prova. Gli stati che solo Claude produce — la ricetta cambiata con la sua
 * riga evidenziata e «Annulla», il messaggio rimasto senza risposta per il limite del
 * piano — li semina `backend/tests/e2e_chat.py` nel container del backend, passando dai
 * servizi veri, e li toglie nel `finally`. Nessuna chiamata a Claude, mai.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const RADICE = fileURLToPath(new URL("../..", import.meta.url));
// gli argomenti come elenco: un percorso o un nome di progetto con uno spazio non cambiano
// il comando
const COMPOSE_E2E = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

type Seminato = { meal_change: string; meal_failed: string };

function aiutanteChat(comando: "seed" | "clean"): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "tests/e2e_chat.py", comando],
    { cwd: RADICE, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("senza token la chat lo dice, e il messaggio resta", async ({ page }) => {
  const trovate = (await (await page.request.get("/api/v1/ingredients/search?q=uova")).json()) as {
    id: string;
    name: string;
  }[];
  const uova = trovate.find((voce) => voce.name === "uova") ?? trovate[0];
  expect(uova, "nessun ingrediente «uova» nel seme").toBeDefined();
  const pasto = await page.request.post("/api/v1/meals", {
    data: { day: giornoDiRoma(2), slot: "dinner", dish: "Frittata di prova chat" },
  });
  expect(pasto.ok()).toBe(true);
  const pastoId = ((await pasto.json()) as { id: string }).id;
  try {
    const ricetta = await page.request.post("/api/v1/recipes", {
      data: {
        title: "Frittata di prova chat",
        instructions: "Sbatti le uova, cuoci in padella.",
        servings: 1,
        source: "manual",
        meal_id: pastoId,
        ingredients: [{ ingredient_id: uova.id, role: "primary", quantity_text: "3" }],
      },
    });
    expect(ricetta.ok()).toBe(true);
    const ricettaId = ((await ricetta.json()) as { id: string }).id;

    await page.goto(`/pasti/${pastoId}`);
    await expect(page.getByRole("heading", { name: "Chat con Claude" })).toBeVisible();
    const avviso = page.getByText("Claude non è collegato: manca la chiave API sul server.");
    await expect(avviso).toBeVisible();

    const campo = page.getByLabel("Messaggio per Claude");
    await campo.fill("quanti spinaci?");
    await page.getByRole("button", { name: "Invia", exact: true }).click();

    await expect(avviso).toBeVisible();
    await expect(campo).toHaveValue("quanti spinaci?");
    const modifica = page.getByRole("link", { name: "Modifica", exact: true });
    await expect(modifica).toBeVisible();
    await modifica.click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}/modifica\\?pasto=${pastoId}$`));

    const chat = await page.request.get(`/api/v1/meals/${pastoId}/chat`);
    expect(chat.ok()).toBe(true);
    expect(((await chat.json()) as { messages: unknown[] }).messages).toHaveLength(0);
  } finally {
    const tolto = await page.request.delete(`/api/v1/meals/${pastoId}`);
    expect.soft([200, 204, 404], `pulizia: il pasto ${pastoId} non si è tolto`).toContain(tolto.status());
  }
});

test("la modifica di Claude si vede, si evidenzia e si annulla", async ({ page }) => {
  const seminato = JSON.parse(aiutanteChat("seed")) as Seminato;
  try {
    await page.goto(`/pasti/${seminato.meal_change}`);
    await expect(page.getByText("Ricetta aggiornata: spinaci congelati, padella unica")).toBeVisible();
    const spinaci = page.locator("li[data-changed]").filter({ hasText: "Spinaci" });
    await expect(spinaci).toHaveCount(1);
    await expect(spinaci).toContainText("150 g");

    await page.getByRole("button", { name: "Annulla", exact: true }).click();

    await expect(page.getByText("Modifica annullata.")).toBeVisible();
    await expect(page.getByText("Ricetta aggiornata: spinaci congelati, padella unica — annullata")).toBeVisible();
    await expect(page.locator("li").filter({ hasText: "Spinaci" }).filter({ hasText: "200 g" })).toHaveCount(1);
    await expect(page.locator("li[data-changed]")).toHaveCount(0);
  } finally {
    aiutanteChat("clean");
  }
});

test("un messaggio senza risposta offre Riprova", async ({ page }) => {
  const seminato = JSON.parse(aiutanteChat("seed")) as Seminato;
  try {
    await page.goto(`/pasti/${seminato.meal_failed}`);
    await expect(page.getByText(/^Claude non risponde: hai raggiunto il limite di frequenza della chiave API, riprova/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Riprova", exact: true })).toBeVisible();
  } finally {
    aiutanteChat("clean");
  }
});

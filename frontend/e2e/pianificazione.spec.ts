import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";
import { giornoDiRoma } from "./giornoDiRoma.ts";

/**
 * La pianificazione con Claude e le schede dei cambi nel browser vero, a 375×812.
 *
 * Lo stack e2e non ha il token di Claude: la chat vera risponde 503, ed è proprio il caso
 * della prima prova. Le proposte e le schede nascono solo quando Claude chiama i suoi
 * strumenti: le semina `backend/tests/e2e_planning.py` nel container del backend, passando
 * dai servizi veri, e le toglie nel `finally` (o nell'`afterAll` della coppia che condivide
 * il seme). Nessuna chiamata a Claude, mai.
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
const SENZA_TOKEN = "Claude non è collegato: manca il token del piano sul server.";
const RICOTTA = "e2e-plan ricotta";
const PARMIGIANO = "e2e-plan parmigiano";
const PIATTO_SCHEDA = "e2e-plan Pasta ricotta e parmigiano";
const BOZZA_PRANZO = "e2e-plan Insalata di farro e ceci";
const BOZZA_CENA = "e2e-plan Merluzzo al forno";

type Seminato = {
  conversation: string;
  proposal_draft: string;
  proposal_official: string;
  card: string;
  meal: string;
};
type VoceDispensa = { id: string; ingredient_name: string; status: string };
type VoceLista = { id: string; ingredient_name: string | null; raw_text: string; status: string };

function aiutantePianificazione(comando: "seed" | "clean"): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "tests/e2e_planning.py", comando],
    { cwd: RADICE, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

function semina(): Seminato {
  return JSON.parse(aiutantePianificazione("seed")) as Seminato;
}

function pulisci() {
  try {
    aiutantePianificazione("clean");
  } catch (guasto) {
    expect.soft(false, `pulizia: non sono riuscito a togliere la semina (${guasto})`).toBe(true);
  }
}

async function dispensa(page: Page, nome: string): Promise<VoceDispensa[]> {
  const risposta = await page.request.get("/api/v1/pantry");
  expect(risposta.ok()).toBe(true);
  return ((await risposta.json()) as VoceDispensa[]).filter((v) => v.ingredient_name === nome);
}

/** Le voci della lista per quell'ingrediente ancora attive: da comprare o nel carrello. */
async function inLista(page: Page, nome: string): Promise<VoceLista[]> {
  const risposta = await page.request.get("/api/v1/shopping-list");
  expect(risposta.ok()).toBe(true);
  return ((await risposta.json()) as VoceLista[]).filter(
    (v) => v.ingredient_name === nome && (v.status === "pending" || v.status === "checked")
  );
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("senza token la pianificazione lo dice, e il testo resta", async ({ page }) => {
  await page.getByRole("link", { name: "Pasti", exact: true }).click();
  await expect(page).toHaveURL(/\/pasti$/);
  await page.getByRole("link", { name: "Pianifica con Claude" }).click();
  await expect(page).toHaveURL(/\/pasti\/pianifica/);
  // l'avviso c'è prima di scrivere; dopo «Invia» c'è anche il rifiuto, con le stesse parole
  await expect(page.getByText(SENZA_TOKEN).first()).toBeVisible();

  const campo = page.getByLabel("Messaggio per Claude");
  await campo.fill("una settimana leggera");
  await page.getByRole("button", { name: "Invia", exact: true }).click();

  await expect(page.getByText(SENZA_TOKEN).first()).toBeVisible();
  await expect(campo).toHaveValue("una settimana leggera");
  await expect(page.getByRole("button", { name: "Nuova", exact: true })).toBeVisible();
});

test("la bozza entra nella settimana", async ({ page }) => {
  const seminato = semina();
  try {
    await page.goto(`/pasti/pianifica?conversazione=${seminato.conversation}`);
    const bozza = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Bozza per la spesa" }) });
    await expect(bozza).toHaveCount(1);
    // la proposta ufficiale di prima è sostituita: la bozza è l'unica da mettere
    await expect(page.getByText("Sostituita da una proposta più nuova.")).toBeVisible();

    await bozza.getByRole("button", { name: "Metti nella settimana" }).click();

    await expect(page.getByText("Pasti messi nella settimana.")).toBeVisible();
    await expect(bozza.getByText("Messa nella settimana.")).toBeVisible();
    // il seguito parte da solo; senza token il 503 lo rimette nel campo, con l'avviso
    const campo = page.getByLabel("Messaggio per Claude");
    await expect(campo).toHaveValue(/^Ho messo nella settimana come bozza: .*Mandami le cose da mettere in lista\.$/);
    await expect(campo).toHaveValue(new RegExp(BOZZA_PRANZO));
    await expect(page.getByText(SENZA_TOKEN).first()).toBeVisible();

    await page.goto(`/pasti?settimana=${giornoDiRoma(30)}`);
    for (const piatto of [BOZZA_PRANZO, BOZZA_CENA]) {
      const pasto = page.getByRole("link", { name: new RegExp(piatto) });
      await expect(pasto).toHaveCount(1);
      await expect(pasto).toContainText("Bozza");
    }
  } finally {
    pulisci();
  }
});

test.describe.serial("la scheda dei cambi seminata", () => {
  let seminato: Seminato;

  test.beforeAll(() => {
    seminato = semina();
  });

  test.afterAll(() => {
    pulisci();
  });

  test("la scheda dei cambi si corregge e si applica una volta", async ({ page }) => {
    await page.goto(`/pasti/cambi/${seminato.card}`);
    await expect(page.getByRole("heading", { name: `Per «${PIATTO_SCHEDA}»` })).toBeVisible();
    const parmigiano = page.getByLabel(`Applica: ${PARMIGIANO}`);
    await expect(parmigiano).toBeChecked();
    await parmigiano.click();
    await expect(parmigiano).not.toBeChecked();

    await page.getByRole("button", { name: "Applica", exact: true }).click();

    await expect(page.getByText("Scheda applicata.")).toBeVisible();
    await expect(page.getByText("Applicata.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Applica", exact: true })).toHaveCount(0);

    const ricotta = await dispensa(page, RICOTTA);
    expect(ricotta.map((v) => v.status)).toEqual(["finished"]);
    const parmigianoInDispensa = await dispensa(page, PARMIGIANO);
    expect(parmigianoInDispensa.map((v) => v.status)).toEqual(["available"]);
    expect(await inLista(page, RICOTTA)).toHaveLength(1);
  });

  test("togliere il pasto propone la scheda inversa", async ({ page }) => {
    await page.goto(`/pasti/${seminato.meal}`);
    await expect(page.getByRole("heading", { name: PIATTO_SCHEDA, level: 1 })).toBeVisible();
    await page.getByRole("button", { name: "Elimina", exact: true }).click();
    await page.getByRole("button", { name: "Sì, elimina", exact: true }).click();

    await expect(page).toHaveURL(/\/pasti\?settimana=/);
    await expect(page.getByText("Schede dei cambi da applicare")).toBeVisible();
    const inversa = page
      .getByRole("listitem")
      .filter({ hasText: `Hai tolto «${PIATTO_SCHEDA}»: rimetti quello che usava?` });
    await expect(inversa).toHaveCount(1);
    await inversa.getByRole("link", { name: "Apri" }).click();

    await expect(page).toHaveURL(/\/pasti\/cambi\/[0-9a-f-]{36}$/);
    await page.getByRole("button", { name: "Applica", exact: true }).click();
    await expect(page.getByText("Scheda applicata.")).toBeVisible();

    const ricotta = await dispensa(page, RICOTTA);
    expect(ricotta.map((v) => v.status)).toEqual(["available"]);
    expect(await inLista(page, RICOTTA)).toHaveLength(0);
  });
});

test("una bozza resa ufficiale a mano apre la scheda vuota", async ({ page }) => {
  const seminato = semina();
  try {
    // i pasti della prova della bozza: messi nella settimana come li mette «Metti nella settimana»
    const messa = await page.request.post(`/api/v1/planning/proposals/${seminato.proposal_draft}/place`, {
      data: { replace: false },
    });
    expect(messa.ok()).toBe(true);
    const pasti = ((await messa.json()) as { meals: { id: string; dish: string; status: string }[] }).meals;
    const pasto = pasti.find((m) => m.dish === BOZZA_CENA);
    expect(pasto?.status).toBe("draft");

    await page.goto(`/pasti/${pasto!.id}`);
    await page.getByRole("button", { name: "Rendi ufficiale", exact: true }).click();

    await expect(page).toHaveURL(/\/pasti\/cambi\/[0-9a-f-]{36}$/);
    await expect(
      page.getByText("Nessuna voce: aggiungi quello che il pasto usa, o scarta la scheda.")
    ).toBeVisible();
    await page.getByLabel("Cerca in dispensa").fill("e2e-plan parm");
    await page.getByRole("button", { name: PARMIGIANO, exact: true }).click();
    await expect(page.getByLabel(`Applica: ${PARMIGIANO}`)).toBeChecked();
    await page.getByRole("button", { name: "Applica", exact: true }).click();
    await expect(page.getByText("Scheda applicata.")).toBeVisible();

    await page.goto(`/pasti/${pasto!.id}`);
    await expect(page.getByRole("heading", { name: BOZZA_CENA, level: 1 })).toBeVisible();
    await expect(page.getByRole("button", { name: "Chiedi la ricetta a Claude" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Scrivi la ricetta" })).toBeVisible();
  } finally {
    pulisci();
  }
});

import { expect, test, type Page } from "@playwright/test";

/**
 * H2, «Attività» e il collegamento con HC Webhook, nel browser vero, a 375×812.
 *
 * Il telefono non c'è: quel che HC Webhook manderebbe lo manda la prova, con `page.request`
 * attraverso Nginx — lo stesso percorso del telefono, compresa la `location` del webhook in
 * `frontend/nginx.conf`. La chiave si crea dalla schermata, come la creerà Mattia, e si
 * legge dal suo campo. Nessuna rete verso fuori.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const WEBHOOK = "/api/v1/activity/hc-webhook";

/** Il giorno di Roma di `giorniFa` giorni fa, `YYYY-MM-DD`. */
function giornoDiRoma(giorniFa: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Rome" }).format(
    new Date(Date.now() - giorniFa * 86_400_000)
  );
}

/** Un corpo come quello di HC Webhook: i passi del giorno in forma «Giornaliero» (la fine
 * porta i millesimi), una corsa di Samsung Health, una pesata, e un tipo che Spena non usa.
 * Le ore sono a metà giornata in UTC: a Roma restano nello stesso giorno, con l'ora legale
 * o senza. */
function corpo(giorno: string) {
  const samsung = { data_origin: "com.sec.android.app.shealth", recording_method: "automatically_recorded" };
  return {
    timestamp: new Date().toISOString(),
    app_version: "e2e",
    steps: [{ count: 12345, start_time: `${giorno}T08:00:00.123Z`, end_time: `${giorno}T20:00:00.456Z` }],
    exercise: [
      {
        type: "56",
        start_time: `${giorno}T16:00:00Z`,
        end_time: `${giorno}T16:30:00Z`,
        duration_seconds: 1800,
        distance_meters: 5200,
        metadata: samsung,
      },
    ],
    weight: [{ kilograms: 72.4, time: `${giorno}T06:00:00Z`, metadata: samsung }],
    heart_rate: [{ bpm: 70, time: `${giorno}T06:00:00Z` }],
  };
}

/** Una chiave nuova dalla schermata: «Crea la chiave», o «Rigenera» se un'altra prova ne
 * ha già creata una. Si legge dal campo «Chiave». */
async function nuovaChiave(page: Page): Promise<string> {
  await page.goto("/attivita/collega");
  const crea = page.getByRole("button", { name: "Crea la chiave" });
  const rigenera = page.getByRole("button", { name: "Rigenera la chiave" });
  await expect(crea.or(rigenera)).toBeVisible();
  if (await rigenera.isVisible()) {
    await rigenera.click();
    await page.getByRole("button", { name: "Rigenera", exact: true }).click();
  } else {
    await crea.click();
  }
  const campo = page.getByLabel("Chiave", { exact: true });
  await expect(campo).toHaveValue(/^[A-Za-z0-9_-]{43}$/);
  return campo.inputValue();
}

/** Copia di `senzaScorrimentoLaterale` in `style.spec.ts` (non esiste un modulo e2e condiviso):
 * se cambia lì, cambia anche qui. */
async function senzaScorrimentoLaterale(page: Page, luogo: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${luogo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("dal ☰ si arriva ad «Attività», e da lì al collegamento coi suoi dieci passi", async ({ page }) => {
  await page.getByRole("button", { name: "Apri il menu" }).click();
  await page.getByRole("dialog", { name: "Menu" }).getByRole("link", { name: "Attività" }).click();

  await expect(page).toHaveURL(/\/attivita$/);
  await expect(page.getByRole("heading", { name: "Attività", level: 1 })).toBeVisible();
  // vuota o no, a seconda di cosa hanno lasciato le altre prove: una delle due strade c'è
  await page.getByRole("link", { name: /^(Collega HC Webhook|Collegamento con HC Webhook)$/ }).click();

  await expect(page).toHaveURL(/\/attivita\/collega$/);
  await expect(page.getByRole("heading", { name: "Collega HC Webhook" })).toBeVisible();
  await expect(page.getByRole("list", { name: "I passi in HC Webhook" }).getByRole("listitem")).toHaveCount(10);
  await expect(page.getByLabel("Indirizzo", { exact: true })).toHaveValue(/\/api\/v1\/activity\/hc-webhook$/);
  for (const pulsante of await page.getByRole("button", { name: /^Copia: / }).all()) {
    expect((await pulsante.boundingBox())!.height, "«Copia»").toBeGreaterThanOrEqual(44);
  }
  await senzaScorrimentoLaterale(page, "il collegamento");
});

test("la chiave apre il webhook: senza o sbagliata è 401, lo stesso corpo due volte salva una volta, e «Attività» lo mostra", async ({
  page,
}) => {
  const chiave = await nuovaChiave(page);
  const dati = corpo(giornoDiRoma(2));

  const senza = await page.request.post(WEBHOOK, { data: dati });
  expect(senza.status(), "senza chiave").toBe(401);
  const sbagliata = await page.request.post(WEBHOOK, { data: dati, headers: { "X-Spena-Token": "x".repeat(43) } });
  expect(sbagliata.status(), "chiave sbagliata").toBe(401);
  for (const volta of [1, 2]) {
    const risposta = await page.request.post(WEBHOOK, { data: dati, headers: { "X-Spena-Token": chiave } });
    expect(risposta.status(), `invio ${volta}`).toBe(200);
    expect(await risposta.json()).toMatchObject({ saved: { steps_days: 1, exercises: 1, weights: 1 } });
  }

  await page.goto("/attivita");
  await expect(page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d\.$/)).toBeVisible();
  await expect(page.getByText(/^Arrivati e non usati: frequenza cardiaca\./)).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Passi degli ultimi 7 giorni" }).getByText("12.345", { exact: true })
  ).toHaveCount(1);
  await expect(
    page.getByRole("list", { name: "Allenamenti degli ultimi 7 giorni" }).getByText("Corsa · 30 min · 5,2 km", { exact: true })
  ).toHaveCount(1);
  await expect(page.getByRole("list", { name: "Ultime pesate" }).getByText("72,4 kg", { exact: true })).toHaveCount(1);
  await senzaScorrimentoLaterale(page, "«Attività»");
});

test("un corpo troppo grosso lo rifiuta il backend, e si legge in «Attività»; la prova di HC Webhook pure", async ({
  page,
}) => {
  const chiave = await nuovaChiave(page);
  const grosso = JSON.stringify({ timestamp: new Date().toISOString(), imbottitura: "x".repeat(3 * 1024 * 1024) });

  const rifiutato = await page.request.post(WEBHOOK, {
    data: grosso,
    headers: { "X-Spena-Token": chiave, "Content-Type": "application/json" },
  });
  // 413 del backend, con la sua frase: Nginx l'ha lasciato passare (4 MB su questa rotta)
  expect(rifiutato.status()).toBe(413);
  expect(await rifiutato.json()).toEqual({
    detail:
      "Rifiutato: il corpo supera i 2 MB. Nel webhook di Spena, in HC Webhook, lascia solo Passi, Sessioni di esercizio e Peso.",
  });
  await page.goto("/attivita");
  await expect(page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d, rifiutata\.$/)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Rifiutato: il corpo supera i 2 MB." })).toBeVisible();

  const prova = await page.request.post(WEBHOOK, {
    data: { ...corpo(giornoDiRoma(0)), test: true },
    headers: { "X-Spena-Token": chiave },
  });
  expect(prova.status()).toBe(200);
  expect(await prova.json()).toMatchObject({ test: true, saved: { steps_days: 0, exercises: 0, weights: 0 } });
  await page.reload();
  await expect(
    page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d, la prova di HC Webhook: arrivata, e non salva niente\.$/)
  ).toBeVisible();
});

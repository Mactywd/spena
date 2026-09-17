import { test, expect } from "@playwright/test";

// L'unico test che attraversa lista, dispensa, ricettario, cottura e rientro in
// lista: tutte le tabelle, un gesto dopo l'altro, sull'app costruita e servita da
// Nginx contro il backend vero. Vuole uno stack pulito (vedi README): riavviarlo
// con `down -v` è parte della prova, perché la lista e la dispensa sono stato.
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test("il ciclo si chiude: lista, dispensa, cottura, ritorno in lista", async ({ page }) => {
  await page.goto("/");

  // l'app parte presumendo una sessione valida: è il primo 401 a far comparire
  // l'accesso, quindi il campo si aspetta invece di darlo per già presente
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();

  // Guardia sullo stato di partenza. Questo percorso scrive in lista e in dispensa:
  // rieseguirlo senza ricreare lo stack trova due «pomodoro» e fallisce con un
  // errore di selettore ambiguo che non dice perché. Detto qui, si capisce.
  await expect(
    page.getByText("Lista vuota. Scrivi cosa ti serve."),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui (vedi README)"
  ).toBeVisible();

  // 1. scrivo la lista scegliendo un ingrediente dall'autocomplete
  await page.getByLabel("Aggiungi alla lista").fill("pomodo");
  await page.getByRole("option", { name: /Pomodoro/ }).click();
  // la casella porta il nome dell'ingrediente abbinato dal backend: asserire su
  // quella, e non su un testo qualsiasi, dice anche che l'abbinamento è avvenuto
  const listed = page.getByRole("checkbox", { name: "pomodoro" });
  await expect(listed).toBeVisible();

  // 2. spunto la voce e la sistemo in dispensa come sfusa
  await listed.click();
  // non `check()`: la casella è controllata dallo stato del server, quindi resta
  // disegnata come prima finché la PATCH non risponde. Aspettare qui è anche la
  // prova che la spunta è arrivata dall'altra parte.
  await expect(listed).toBeChecked();
  await page.getByRole("link", { name: "Sistema la spesa" }).click();
  await page.getByRole("button", { name: /Sfuso.*pomodoro/i }).click();
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();

  // 3. la dispensa la mostra disponibile. Lo stato lo dice la pastiglia
  // (StatusChip), non più tre pulsanti: il cursore a fianco è solo un'indicazione
  // a occhio e non porta l'aria-pressed di un controllo scelto.
  await expect(page.getByRole("heading", { name: "Dispensa" })).toBeVisible();
  const pantryRow = page.locator("li", { hasText: "pomodoro" }).first();
  await expect(pantryRow.getByText("Disponibile", { exact: true })).toBeVisible();

  // 4. apro una ricetta del seme e la cucino, dichiarando il pomodoro finito
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByLabel("Cerca nel ricettario").fill("pomodoro");
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).click();
  await page.getByRole("button", { name: "Cucina", exact: true }).click();
  const row = page.locator("li", { hasText: "pomodoro" }).first();
  // `exact` non è decorativo: senza, «Finito» corrisponde anche a «Quasi finito»
  // (il nome accessibile si cerca come sottostringa) e il selettore è ambiguo
  await row.getByRole("button", { name: "Finito", exact: true }).click();
  await expect(row.getByRole("checkbox", { name: /Rimetti in lista/ })).toBeChecked();
  await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
  // il conto viene dal backend: è lui a sapere quante voci sono rientrate
  await expect(page.getByRole("status")).toHaveText(
    "Segnato. Una cosa è tornata in lista della spesa."
  );

  // 5. il cerchio si chiude: il pomodoro è tornato in lista da sé
  await page.getByRole("link", { name: "Lista", exact: true }).click();
  // il motivo è scritto accanto alla voce, non in un tooltip: da telefono il
  // passaggio del mouse non esiste (vedi ShoppingListScreen.tsx)
  await expect(page.getByText("rientrata perché finita cucinando")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "pomodoro" })).not.toBeChecked();
});

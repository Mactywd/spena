import { test, expect } from "@playwright/test";

/**
 * A cosa serve questo file: provare un ramo d'errore sull'app vera, costruita e
 * servita da Nginx, con un browser vero e una risposta d'errore vera.
 *
 * La storia che lo motiva. I test dei singoli schermi girano in jsdom e ognuno
 * costruisce il proprio QueryClient con `retry: false`. Per cinque revisioni sono
 * stati tutti verdi mentre il client vero di src/App.tsx ritentava ogni errore
 * non-401 all'infinito: `isError` non diventava mai vero e nessun messaggio
 * d'errore era raggiungibile — lo schermo restava su «Carico…» per sempre
 * (corretto in a623025). La differenza non stava nel messaggio ma nella politica
 * di ritentativo, che un test con il proprio client non può vedere.
 *
 * Quel difetto preciso ha già una guardia in jsdom: src/App.test.tsx monta <App />
 * con il suo QueryClient e un fetch finto. Questo test aggiunge ciò che quella
 * guardia non può avere: il bundle di produzione (React minificato), il fetch del
 * browser con il cookie di sessione vero, e un errore che arriva davvero dalla rete
 * — attraverso il proxy /api/ di Nginx e il backend — invece di essere inventato da
 * uno stub. Per questo la richiesta viene deviata su un percorso API inesistente con
 * `continue` e non falsificata con `fulfill`: così la risposta d'errore la produce
 * il server, e la catena che la porta sullo schermo è quella intera.
 */

const PASSWORD = process.env.E2E_PASSWORD ?? "test";

// Con la politica giusta (`count < 2`) l'errore compare dopo tre tentativi e due
// attese di react-query, 1s e 2s: circa 3 secondi. Con un ritentativo infinito i
// tentativi cadono a 0s, 1s, 3s, 7s, 15s e l'errore non compare mai. 10 secondi
// sta sopra il primo caso e sotto il secondo: misurato rimettendo il difetto di
// a623025, il test fallisce a circa 10s invece di restare appeso per sempre.
const ERROR_SHOWS_WITHIN_MS = 10_000;

test("un errore del server diventa un messaggio leggibile, non un «Carico…» eterno", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  // l'accesso deve essere andato a buon fine prima di rompere la lista: altrimenti
  // si proverebbe il ramo sbagliato, cioè la schermata di accesso
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  // Un 404 dal backend, non un 401: il 401 è una sessione scaduta e riporta
  // all'accesso per disegno, mentre qualunque altro errore è il caso che deve
  // diventare un messaggio. La deviazione resta attiva anche sui ritentativi.
  await page.route("**/api/v1/shopping-list?**", (route) =>
    route.continue({ url: new URL("/api/v1/rotta-che-non-esiste", page.url()).toString() })
  );
  await page.reload();

  await expect(page.getByRole("alert")).toContainText(
    "Non sono riuscito a caricare la lista",
    { timeout: ERROR_SHOWS_WITHIN_MS }
  );
  // e non è un vicolo cieco: si può continuare a scrivere in lista
  await expect(page.getByLabel("Aggiungi alla lista")).toBeEnabled();
});

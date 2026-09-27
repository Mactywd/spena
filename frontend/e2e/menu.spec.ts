import { test, expect } from "@playwright/test";

/**
 * Il velo e il pannello del ☰ (Task 13) vanno in un portale su `document.body`
 * (ruling F4): l'intestazione è `sticky top-0 z-10`, uno stacking context suo, e su
 * `/lista` il modulo sticky per aggiungere una voce (`AddItemField`, anch'esso `z-10`
 * ma dopo nel DOM) dipingerebbe sopra il velo e la cima del pannello — coprendo «Sistema
 * la spesa» — se menu e velo restassero dentro l'header invece che nel portale.
 *
 * Nessun test in jsdom vede questo: jsdom non calcola gli stacking context CSS, quindi
 * un test di componente vedrebbe il link nell'albero accessibile e lo cliccherebbe a
 * prescindere da cosa lo ricopre visivamente. Qui, nel browser vero, un tocco sul primo
 * link naviga solo se il link è davvero sopra — se il modulo lo coprisse il tocco
 * arriverebbe a quello, e la navigazione a `/sistema` non avverrebbe.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/lista");
  // l'app parte presumendo una sessione valida: è il primo 401 a far comparire
  // l'accesso, quindi il campo si aspetta invece di darlo per già presente
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("il ☰ apre il menu su /lista, e la prima voce ci porta davvero, non al modulo sotto", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Apri il menu" }).click();

  const menu = page.getByRole("dialog", { name: "Menu" });
  await expect(menu).toBeVisible();

  const primaVoce = menu.getByRole("link", { name: "Sistema la spesa" });
  await expect(primaVoce).toBeVisible();
  await primaVoce.click();

  await expect(page).toHaveURL(/\/sistema$/);
  await expect(page.getByRole("heading", { name: "Sistema la spesa" })).toBeVisible();
});

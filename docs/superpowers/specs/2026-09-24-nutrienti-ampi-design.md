# S4 — Valori nutrizionali molto più ampi

Data: 2026-09-24. Voce di `docs/prossimi-passi.md`: **S4**. Il TODO sui campi (quali
macro/micronutrienti, con che unità e riferimenti giornalieri) è stato risolto da una
ricerca dedicata nella conversazione dello stesso giorno; questa spec ne prende le
conclusioni e decide cosa costruire davvero, oggi, e cosa resta apposta fuori.

## 1. Cosa c'è già, e cosa manca

`products.nutrients` è già un JSONB libero (`dict[str, float] | None`,
`backend/app/db/models/product.py`), popolato da Open Food Facts tramite
`_NUTRIENT_MAP` (`backend/app/services/openfoodfacts.py:17`): otto chiavi — kcal,
protein, carbs, sugars, fat, saturated_fat, fiber, salt. Non serve una migrazione per
allargare il vocabolario: la colonna accetta già qualunque chiave.

**Ma nessuno schermo mostra un nutriente, oggi.** `CustomProductForm.tsx` ha quattro
campi modificabili (kcal, proteine, carboidrati, grassi) e "trasporta" in silenzio gli
altri quattro che arrivano da Open Food Facts, senza mai disegnarli — il commento nel
file lo dice già: sono «quattro campi in più da leggere su un telefono, per dati che
nessuno correggerà a mano». Nessuna schermata di dispensa, ricetta o prodotto legge
`nutrients` per mostrarlo. Chi userà davvero questi dati è **P2** (NutriScore), che
oggi non esiste.

**Decisione di scopo.** S4 qui non costruisce un cruscotto nutrizionale — non ha
ancora un lettore vero. Costruisce la **base dati**: un vocabolario di campi deciso
una volta, la loro raccolta da Open Food Facts dove disponibile, e il posto dove P2
andrà a leggerli. È lo stesso ragionamento di R9, che chi legge davvero il costo è P3:
la voce viene prima perché è piccola e indipendente, e perché ogni prodotto scansionato
oggi senza micronutrienti andrebbe riscansionato dopo.

## 2. Le decisioni

1. **Un vocabolario canonico, scritto una volta, in un modulo di dominio.**
   `backend/app/domain/nutrients.py`, puro come `rules.py` e `quantities.py`: nessun
   accesso al database. Contiene, per ciascun campo, la chiave (`kcal`, `vitamin_c`,
   `calcium`, …), l'unità (`kcal`, `g`, `mg`, `µg`), l'etichetta italiana, e il VNR
   (valore nutritivo di riferimento) per un adulto — dall'**Allegato XIII del
   Regolamento UE 1169/2011** (parte A: vitamine e minerali; parte B: energia e
   macronutrienti), la stessa normativa dell'etichetta nutrizionale italiana. Il VNR non serve a nessun conto oggi: è scritto perché quando P2 dovrà
   calcolare un punteggio, la tabella sia già lì, normata e non improvvisata — lo
   stesso spirito di `LOW_MAX_FILL` ed `EXPIRY_SOON_DAYS`: **una costante di dominio
   sola, non ricopiata**.
2. **Due livelli restano due livelli, e solo uno si costruisce ora.** Il TBD
   strutturale di `prossimi-passi.md` — prodotto (esatto, da Open Food Facts) contro
   ingrediente generico (medio, da tabelle come CREA) — **resta un TBD**. La ricerca
   ha verificato che CREA non ha un'API né un export ufficiale, solo consultazione
   web: popolarlo è un lavoro di scraping o inserimento a mano, non un import in
   blocco, e non è oggi materia di questa spec. **S4 costruisce solo il livello
   prodotto.** Il campo che porterà il livello ingrediente resterà su
   `ingredients` quando arriverà; non esiste ancora.
3. **Priorità di popolamento: quattro campi, non tutto il vocabolario.** Open Food
   Facts copre male i micronutrienti — secondo la ricerca meno del 20% dei prodotti
   ne porta oltre al sodio; è un dato riportato, non misurato da noi — quindi
   allargare `_NUTRIENT_MAP` a tutti e ventisette i micronutrienti dell'Allegato XIII
   riempirebbe quasi sempre il vuoto. Si aggiungono i quattro con
   la copertura migliore e la rilevanza più immediata in una dieta italiana comune:
   **vitamina C, calcio, ferro, potassio**. Gli altri ventitré restano nel vocabolario
   (per nome, unità, VNR) ma **non si raccolgono ancora**: quando un giorno arriverà
   una fonte più ricca (CREA, o Open Food Facts che migliora), si aggiunge una riga
   alla mappa, non uno schema.
4. **Niente di nuovo nel modulo manuale.** `CustomProductForm.tsx` non guadagna
   campi: nessuno batte a mano il proprio apporto di ferro su un telefono, ed è
   esattamente la ragione per cui gli extra esistenti sono già invisibili e solo
   trasportati. I quattro nuovi campi si comportano come i quattro extra di oggi —
   arrivano da Open Food Facts, si salvano, si nominano nella riga «Da Open Food
   Facts vengono salvati anche…» — e basta.
5. **Niente display nutrienti in questa spec.** Nessuna schermata nuova, nessun
   %VNR calcolato. Sarebbe un cruscotto senza un punteggio a cui servire, e un
   numero che nessuno guarderebbe finché P2 non esiste — il rischio già scritto per
   S4 stesso: «un punteggio calcolato su dati parziali deve dire di esserlo», cosa
   che qui non c'è ancora nulla da dire.

## 3. Il vocabolario

`backend/app/domain/nutrients.py`, una `NamedTuple` (o `dataclass(frozen=True)`) per
campo e un dizionario `NUTRIENT_FIELDS: dict[str, NutrientField]`, chiave = lo stesso
nome usato in `products.nutrients`:

| Chiave | Etichetta | Unità | VNR (adulto) | Raccolto oggi |
|---|---|---|---|---|
| `kcal` | Energia | kcal | 2000 | sì |
| `protein` | Proteine | g | 50 | sì |
| `carbs` | Carboidrati | g | 260 | sì |
| `sugars` | di cui zuccheri | g | 90 | sì |
| `fat` | Grassi | g | 70 | sì |
| `saturated_fat` | di cui saturi | g | 20 | sì |
| `fiber` | Fibre | g | — (nessun VNR normato) | sì |
| `salt` | Sale | g | 6 | sì |
| `vitamin_c` | Vitamina C | mg | 80 | **nuovo** |
| `calcium` | Calcio | mg | 800 | **nuovo** |
| `iron` | Ferro | mg | 14 | **nuovo** |
| `potassium` | Potassio | mg | 2000 | **nuovo** |
| `vitamin_a` … `iodine` | (i restanti 23 micronutrienti dell'Allegato XIII) | mg/µg | dall'Allegato XIII | no — solo vocabolario |

Sono 35 voci: le sette della parte B, le fibre (che il regolamento non norma) e i
ventisette micronutrienti della parte A. La tabella completa, con i valori esatti, va
nel modulo, non
ripetuta qui: è dati, non narrazione, e un domani P2 la importa con
`from app.domain.nutrients import NUTRIENT_FIELDS`.

## 4. La raccolta

`_NUTRIENT_MAP` in `openfoodfacts.py` si allarga di quattro righe:

```python
"vitamin-c_100g": "vitamin_c",
"calcium_100g": "calcium",
"iron_100g": "iron",
"potassium_100g": "potassium",
```

Stesso meccanismo di oggi: un nutriente assente nella risposta OFF resta assente nel
dizionario, mai un valore a zero. Nessuna migrazione: `products.nutrients` è già
JSONB libero.

**Le unità.** Open Food Facts scrive ogni campo `_100g` **in grammi**, qualunque
unità mostri l'etichetta — misurato il 2026-09-24 su prodotti veri: il ferro dei
Chocapic arriva come `0.012`, la vitamina D come `3.1e-06`. L'energia in kcal è
l'unica eccezione. La raccolta quindi converte ogni valore all'unità che il vocabolario
dichiara per quella chiave (×1000 per i mg, ×1.000.000 per i µg), così
`products.nutrients` dice sempre `{"iron": 12}` intendendo 12 mg, e chi lo leggerà
non dovrà sapere da quale fonte è arrivato. La prima stesura di questa spec non lo
diceva, e la prima implementazione salvava i grammi sotto una chiave in mg: corretto
lo stesso giorno, prima che un solo prodotto in produzione ne fosse toccato.

## 5. Lo schermo

Un solo cambiamento, in `CustomProductForm.tsx`: `EXTRA_LABELS` guadagna le quattro
chiavi nuove, così la riga «Da Open Food Facts vengono salvati anche…» le nomina in
italiano invece di mostrare la chiave grezza se mai comparissero prima che qualcuno
ci pensi:

```ts
const EXTRA_LABELS: Record<string, string> = {
  sugars: "zuccheri",
  saturated_fat: "grassi saturi",
  fiber: "fibre",
  salt: "sale",
  vitamin_c: "vitamina C",
  calcium: "calcio",
  iron: "ferro",
  potassium: "potassio",
};
```

Nessun altro file di frontend cambia.

## 6. Fuori

- **Il livello ingrediente generico (CREA).** Resta un TBD dichiarato, non aperto da
  questa spec: manca una fonte con un'API o un export, e affrontarlo qui vorrebbe
  dire decidere uno scraper prima di sapere se serve davvero a P2 o a M1 subito o più
  avanti.
- **Il tasto «Stima» con l'AI.** TBD invariato: quale modello, se basta Gemma o serve
  accesso al web via OpenRouter — va deciso quando la spec di quel tasto si scrive,
  non qui.
- **Ogni display, calcolo o %VNR.** Non ha lettore prima di P2.
- **I restanti ventitré micronutrienti dell'Allegato XIII.** Nel vocabolario per nome, non
  raccolti: si aggiungono quando una fonte li riempie per davvero.

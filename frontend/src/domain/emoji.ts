/** Le figure che un ingrediente può avere in Dispensa (S12), nell'ordine della griglia di
 * «Cambia figura» in Anagrafica.
 *
 * È una copia di `INGREDIENT_EMOJI` in `backend/app/domain/emoji.py`, che è l'originale e
 * dice perché l'elenco è chiuso e fermo a Emoji 14.0; `backend/tests/test_frontend_emoji.py`
 * le confronta voce per voce. Il frontend non decide niente con questo elenco: lo offre da
 * scegliere, e il server verifica la scelta.
 */
export const INGREDIENT_EMOJI = [
  // frutta
  "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🫐",
  "🥝", "🍅", "🫒", "🥥",
  // verdura, legumi, frutta secca, erbe
  "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🫑", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🫘",
  "🌰", "🌿", "🌱", "🌾",
  // pane e forno
  "🍞", "🥐", "🥖", "🫓", "🥨", "🥯", "🥞", "🧇",
  // formaggi, carne, uova, piatti
  "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🫔", "🥙", "🧆",
  "🥚", "🍳", "🥘", "🍲", "🫕", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫",
  // cucina asiatica
  "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟",
  "🥠", "🥡",
  // pesce e mare
  "🦀", "🦞", "🦐", "🦑", "🦪", "🐟", "🐙", "🐚",
  // dolci
  "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯",
  // bevande e barattoli
  "🍼", "🥛", "☕", "🫖", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🥂", "🥃", "🫗", "🥤",
  "🧋", "🧃", "🧉", "🧊", "🫙",
  // casa e igiene
  "🧻", "🧽", "🧴", "🧼", "🪥", "🪒", "🧹", "🧺", "🪣", "🧤", "🧷", "🩹", "💊", "🕯️", "💡",
  "🔋", "🗑️",
] as const;

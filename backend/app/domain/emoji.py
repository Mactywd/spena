"""Le figure degli ingredienti in Dispensa (S12): l'elenco chiuso, e la sua verifica.

Bozza `docs/superpowers/specs/2026-10-06-righe-dispensa-bozza.md`, §3.A e §5. Un
ingrediente ha al più un'emoji, scelta da questo elenco e da nessun altro posto: dall'AI
(`python -m app.cli.decide_emoji`) o a mano in Anagrafica. L'elenco è fermo a **Emoji
14.0** (2021, deciso da Mattia il 2026-10-07): una figura più recente, su un telefono non
aggiornato, diventa un quadratino vuoto, che è peggio del ripiego. Restano fuori per
questo 🫚 zenzero e 🫛 baccello (15.0) e le sequenze della 15.1 (il lime, il fungo
marrone), che sono le prime che un modello proporrebbe.

Sta nel dominio e non in un servizio perché i punti che scrivono la colonna sono due —
il servizio dell'anagrafica e quello dell'AI — e la stessa verifica deve valere per
tutti e due (prima lezione di CLAUDE.md). Il frontend ne tiene una copia,
`frontend/src/domain/emoji.ts`, solo per offrire la griglia di «Cambia figura»:
`backend/tests/test_frontend_emoji.py` la confronta con questa, voce per voce e
nell'ordine.

`ingredients.emoji` ha tre stati, non due:
- `NULL`: nessuno ha ancora deciso. La riga mostra l'icona del reparto, e il comando
  dell'AI la chiederà;
- `NO_EMOJI`, la stringa vuota: qualcuno ha deciso che nessuna figura dell'elenco va
  bene — l'AI rispondendo «nessuna», o una persona scegliendo «Nessuna» in Anagrafica.
  A video è identica a `NULL`, ma l'AI non la chiede più: scrive solo dove è `NULL`, e
  così una scelta fatta a mano non si riscrive mai (bozza §3.A);
- un'emoji dell'elenco.
Fuori dal backend esce solo `None` o un'emoji (`shown_emoji`): la stringa vuota è un
dettaglio della colonna, e il client non ha motivo di conoscerlo.
"""

# La larghezza della colonna. La figura più lunga dell'elenco è di due code point
# (l'emoji e il selettore di variante U+FE0F): sedici lasciano margine senza invitare a
# scriverci altro.
EMOJI_MAX_LENGTH = 16

NO_EMOJI = ""

# Il selettore di variante «disegnala come emoji». Tre voci lo portano (peperoncino,
# candela, cestino): senza, alcuni sistemi le mostrano come simboli in bianco e nero.
_VS16 = "️"

# Nell'ordine della griglia dell'Anagrafica, per famiglie: chi cerca la carota la trova
# vicino alle altre verdure. Le figure «di famiglia» (🧀 per ogni formaggio, 🐟 per ogni
# pesce) sono volute: la bozza le conta come figure, e sono meglio del ripiego.
INGREDIENT_EMOJI: tuple[str, ...] = (
    # frutta
    "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🫐",
    "🥝", "🍅", "🫒", "🥥",
    # verdura, legumi, frutta secca, erbe
    "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🫑", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🫘",
    "🌰", "🌿", "🌱", "🌾",
    # pane e forno
    "🍞", "🥐", "🥖", "🫓", "🥨", "🥯", "🥞", "🧇",
    # formaggi, carne, uova, piatti
    "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🫔", "🥙", "🧆",
    "🥚", "🍳", "🥘", "🍲", "🫕", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫",
    # cucina asiatica
    "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟",
    "🥠", "🥡",
    # pesce e mare
    "🦀", "🦞", "🦐", "🦑", "🦪", "🐟", "🐙", "🐚",
    # dolci
    "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯",
    # bevande e barattoli
    "🍼", "🥛", "☕", "🫖", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🥂", "🥃", "🫗", "🥤",
    "🧋", "🧃", "🧉", "🧊", "🫙",
    # casa e igiene
    "🧻", "🧽", "🧴", "🧼", "🪥", "🪒", "🧹", "🧺", "🪣", "🧤", "🧷", "🩹", "💊", "🕯️", "💡",
    "🔋", "🗑️",
)

_BY_BARE = {voce.replace(_VS16, ""): voce for voce in INGREDIENT_EMOJI}


def canonical_emoji(value: str) -> str | None:
    """La voce dell'elenco che `value` scrive, o `None` se non è nell'elenco.

    Il selettore di variante può esserci o no: «🌶» e «🌶️» sono la stessa figura, e un
    modello o una tastiera a volte lo omettono. Si torna sempre la forma dell'elenco,
    così la colonna ne ha una sola. Gli spazi ai lati non contano."""
    bare = value.strip().replace(_VS16, "")
    return _BY_BARE.get(bare) if bare else None


def shown_emoji(stored: str | None) -> str | None:
    """Quel che la colonna dice a chi guarda: un'emoji, o `None` per il ripiego."""
    return stored or None

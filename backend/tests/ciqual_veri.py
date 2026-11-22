"""Alimenti veri di CIQUAL 2025, per provare l'ordine dei candidati (S4).

Nomi, gruppi e codici sono quelli del file del 2025, l'a capo compreso, come lo legge
`read_ciqual`; i nutrienti sono vuoti, perché qui non contano. Servono a riprodurre la
parità di `word_similarity` che il pilota del 2026-10-20 ha incontrato sulla tabella
vera — «riz» vale 1 con ogni nome che lo contiene — e che quattro righe inventate non
fanno mai vedere.

`tabella_vera` carica invece il file intero del repository
(`data/ciqual/ciqual-2025.xlsx`) per la stessa strada di `load_ciqual`: `read_ciqual`
e `upsert_foods`.

Si importa come `llm_fakes`: `from ciqual_veri import ALIMENTI_VERI, tabella_vera`
(pytest mette `tests/` in `sys.path`).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.cli.load_ciqual import CANDIDATE_FILES
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods
from app.services.ciqual_file import read_ciqual

ALIMENTI_VERI = [
    CiqualRow("4041", "Aligot (purée de pomme de terre à la tomme fraîche),\npréemballé", "plats composés", {}),
    CiqualRow("96781", "Amidon de riz", "farines", {}),
    CiqualRow("37002", "Base de pizza (pâte et sauce à la tomate), crue", "aides culinaires", {}),
    CiqualRow("18904", "Boisson au riz, nature, préemballée", "boissons sans\nalcool", {}),
    CiqualRow("25559", "Brick à la pomme de terre, fait maison, cuit", "feuilletées et autres\nentrées", {}),
    CiqualRow("76039", "Eau minérale Salvetat, embouteillée, gazeuse,\nmoyennement minéralisée (La Salvetat, 34)", "eaux", {}),
    CiqualRow("9520", "Farine de riz", "farines", {}),
    CiqualRow("4090", "Fécule de pomme de terre", "farines", {}),
    CiqualRow("11082", "Fleur de sel, non iodée, non fluorée", "sels", {}),
    CiqualRow("20194", "Haricots blancs à la sauce tomate, appertisés", "plats composés", {}),
    CiqualRow("19590", "Mozzarella au lait de vache", "fromages et\nalternatives\nvégétales", {}),
    CiqualRow("25464", "Pizza au saumon, préemballée", "pizzas, tartes et\ncrêpes salées", {}),
    CiqualRow("4003", "Pomme de terre, bouillie/cuite à l'eau", "pommes de terre et\nautres tubercules", {}),
    CiqualRow("4008", "Pomme de terre, sans peau, crue", "pommes de terre et\nautres tubercules", {}),
    CiqualRow("39251", "Riz au lait, au caramel, rayon frais", "produits laitiers frais\net alternatives\nvégétales", {}),
    CiqualRow("9100", "Riz blanc, cru", "pâtes, riz et\ncéréales", {}),
    CiqualRow("9104", "Riz blanc, cuit, sans sel ajouté", "pâtes, riz et\ncéréales", {}),
    CiqualRow("26263", "Salade de riz au thon et légumes, avec sauce,\npréemballée", "salades composées\net crudités", {}),
    CiqualRow("12725", "Salers", "fromages et\nalternatives\nvégétales", {}),
    CiqualRow("26036", "Saumon, élevage, cru", "poissons crus", {}),
    CiqualRow("26229", "Saumon, grillé/poêlé", "poissons cuits", {}),
    CiqualRow("11017", "Sel blanc alimentaire, non iodé, non fluoré (marin,\nignigène ou gemme)", "sels", {}),
    CiqualRow("11083", "Sel marin gris, non iodé, non fluoré", "sels", {}),
    CiqualRow("25555", "Tarte au saumon, préemballée", "pizzas, tartes et\ncrêpes salées", {}),
    CiqualRow("26039", "Thon, au naturel, appertisé, égoutté", "produits à base de\npoissons et produits\nde la mer", {}),
    CiqualRow("26053", "Thon, cru", "poissons crus", {}),
    CiqualRow("20358", "Tomate, chair et peau, cuite (aliment moyen)", "légumes", {}),
    CiqualRow("20385", "Tomate sans précision, crue (aliment moyen)", "légumes", {}),
]


async def tabella_vera(session: AsyncSession) -> int:
    """Il file del repository nel database, per la strada di `load_ciqual`; quanti
    alimenti ha scritto."""
    return await upsert_foods(session, read_ciqual(CANDIDATE_FILES[0]).foods)

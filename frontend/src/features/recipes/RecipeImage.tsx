import { useState } from "react";

/** La foto di una ricetta, con il buco già chiuso.
 *
 * L'immagine arriva dal server di origine e non viene mai copiata (spec §6.3): un
 * 404 dopo che la ricetta è stata rinominata altrove, un blocco sul Referer, o solo
 * il segnale debole del corridoio del supermercato sono il caso normale, non
 * l'eccezione. Quando il caricamento fallisce, chi la usa si comporta come se
 * `image_url` fosse stato null da sempre — lo stesso disegno già pensato e già
 * provato per quel caso, non un terzo stato da inventare.
 *
 * Sta in un componente suo perché i posti che la mostrano sono due, la scheda
 * dell'elenco e la ricetta aperta, e la seconda copia di questa logica si
 * scollerebbe proprio sul ramo che nessuno guarda: quello dell'immagine rotta.
 */
export function RecipeImage({
  url,
  alt,
  className = "",
}: {
  url: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (url === null || failed) return null;

  return (
    <img
      src={url}
      alt={alt}
      // duecento schede su un telefono sono duecento immagini
      loading="lazy"
      onError={() => setFailed(true)}
      className={className}
    />
  );
}

import { useEffect, useId, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { draftVariant } from "../recipes/api";
import { aiNoticeOf } from "../../api/aiNotice";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IconSparkles } from "../../components/ui/icons";
import { VARIANT_PANEL_ID, variantPath, type VariantState } from "./variantState";
import type { RecipeDetail } from "../../domain/types";

/** Il pannello di «Modifica con AI» nel dettaglio di una ricetta (R8): la richiesta, e la
 * proposta che apre il modulo della variante.
 *
 * Sta nel dettaglio dell'originale e non in uno schermo suo perché, se l'AI non risponde,
 * si resta sull'originale (Mattia, 2026-10-09): la ricetta è lì sotto, intera, e funziona
 * com'era. Il guasto ha il colore di ogni guasto dell'AI, l'ambra di `tone="degraded"`. */
export function VariantPrompt({ recipe, onClose }: { recipe: RecipeDetail; onClose: () => void }) {
  const navigate = useNavigate();
  const fieldId = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const [prompt, setPrompt] = useState("");
  const propose = useMutation({
    mutationFn: (request: string) => draftVariant(recipe.id, request),
  });

  // aperto il pannello, si scrive: il fuoco va nel campo
  useEffect(() => {
    fieldRef.current?.focus();
  }, []);

  function submit() {
    const request = prompt.trim();
    // La navigazione sta nelle callback di `mutate` e non nelle opzioni di `useMutation`:
    // quelle di `mutate` non partono se il pannello si è chiuso nel frattempo («Annulla»
    // con la proposta in volo), e una proposta rinunciata non deve aprire il modulo.
    propose.mutate(request, {
      onSuccess: (draft) => {
        const state: VariantState = {
          prompt: request,
          draft,
          originTitle: recipe.title,
          originCategory: recipe.category,
        };
        navigate(variantPath(recipe.id), { state });
      },
    });
  }

  return (
    <Card className="mt-3">
      <div id={VARIANT_PANEL_ID} className="flex flex-col gap-2">
        <label htmlFor={fieldId} className="text-sm text-ink-soft">
          Cosa vuoi cambiare?
        </label>
        <textarea
          id={fieldId}
          ref={fieldRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          // il limite di `DraftRequest` nel backend: oltre, il server risponderebbe 422
          maxLength={1000}
          placeholder="Sostituisci lo zucchero con il dolcificante"
        />
        <p className="text-xs text-ink-soft">
          L'AI scrive una ricetta nuova, che correggi prima di salvare. Questa resta com'è.
        </p>
        {/* secondario: il primario della vista resta «Cucina». Da solo, quindi icona e
            testo (spec T3 §2); «non ancora» col perché sotto, `busy` in volo */}
        <Button
          variant="secondary"
          shape="block"
          icon={IconSparkles}
          busy={propose.isPending}
          unavailableReason={
            prompt.trim().length < 3 ? "Scrivi cosa cambiare: bastano tre lettere." : undefined
          }
          onClick={submit}
        >
          {propose.isPending ? "Propongo…" : "Proponi la variante"}
        </Button>
        {propose.isError && (
          <Alert tone="degraded">
            {aiNoticeOf(propose.error) !== null
              ? `${aiNoticeOf(propose.error)} Questa ricetta resta com'è.`
              : "L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco."}
          </Alert>
        )}
        <Button variant="ghost" onClick={onClose}>
          Annulla
        </Button>
      </div>
    </Card>
  );
}

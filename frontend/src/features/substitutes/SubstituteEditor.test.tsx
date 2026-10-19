import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { ApiError } from "../../api/client";
import type { Ingredient } from "../../domain/types";
import { SubstituteEditor } from "./SubstituteEditor";
import type { Substitute, SubstitutionBody, SubstitutionVerdict } from "./types";

const RISO: Substitute = { ingredient_id: "i-riso", name: "riso", note: "cottura più lunga" };
const FARRO: Substitute = { ingredient_id: "i-farro", name: "farro", note: null };
const ORZO: Substitute = { ingredient_id: "i-orzo", name: "orzo", note: null };
const RISO_IN_ANAGRAFICA: Ingredient = {
  id: "i-riso", name: "riso", display_name: "Riso", category: "cereali", kind: "food",
};

function renderEditor({
  initialVerdict = null,
  initialSubstitutes = [],
  save = vi.fn(async (body: SubstitutionBody) => body),
}: {
  initialVerdict?: SubstitutionVerdict | null;
  initialSubstitutes?: Substitute[];
  save?: (body: SubstitutionBody) => Promise<unknown>;
} = {}) {
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  const client = createTestQueryClient();
  render(
    <QueryClientProvider client={client}>
      <SubstituteEditor
        legend="Al posto di pasta, in questa ricetta:"
        saveLabel="Salva per questa ricetta"
        initialVerdict={initialVerdict}
        initialSubstitutes={initialSubstitutes}
        save={save}
        onSaved={onSaved}
        onCancel={onCancel}
      />
    </QueryClientProvider>
  );
  return { save, onSaved, onCancel };
}

function stubSearch() {
  const spy = vi.fn((url: unknown) =>
    Promise.resolve(
      new Response(
        JSON.stringify(String(url).includes("/ingredients/search") ? [RISO_IN_ANAGRAFICA] : []),
        { status: 200 }
      )
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SubstituteEditor", () => {
  it("parte dalla risposta di prima", () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    expect(screen.getByRole("group", { name: "Al posto di pasta, in questa ricetta:" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Un altro ingrediente" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("cottura più lunga");
  });

  it("senza sostituti «Salva» dice perché, e non salva", async () => {
    const { save } = renderEditor();
    const salva = screen.getByRole("button", { name: "Salva per questa ricetta" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scegli almeno un ingrediente.")).toBeInTheDocument();
    await userEvent.click(salva);
    expect(save).not.toHaveBeenCalled();
  });

  it("si sceglie dal cibo dell'anagrafica, e lo stesso una volta sola", async () => {
    const spy = stubSearch();
    renderEditor();
    await userEvent.type(screen.getByRole("textbox", { name: "Cosa usare al suo posto" }), "ris");
    await userEvent.click(await screen.findByRole("option", { name: "Riso" }));
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("");
    expect(String(spy.mock.calls.at(-1)?.[0])).toContain("kind=food");

    await userEvent.type(screen.getByRole("textbox", { name: "Aggiungine un altro" }), "ris");
    await userEvent.click(await screen.findByRole("option", { name: "Riso" }));
    expect(screen.getAllByRole("textbox", { name: "Nota per riso" })).toHaveLength(1);
  });

  it("con tre sostituti non ne offre un quarto", () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO, FARRO, ORZO] });
    expect(screen.queryByRole("textbox", { name: "Aggiungine un altro" })).toBeNull();
  });

  it("manda l'esito e i sostituti con le note", async () => {
    const { save, onSaved } = renderEditor({
      initialVerdict: "substitutes", initialSubstitutes: [{ ...RISO, note: null }, FARRO],
    });
    await userEvent.type(screen.getByRole("textbox", { name: "Nota per riso" }), "metà dose");
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    const atteso = {
      verdict: "substitutes",
      substitutes: [{ ingredient_id: "i-riso", note: "metà dose" }, { ingredient_id: "i-farro", note: null }],
    };
    expect(save).toHaveBeenCalledWith(atteso);
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(atteso));
  });

  it("«Si può omettere» non manda sostituti", async () => {
    const { save } = renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    await userEvent.click(screen.getByRole("radio", { name: "Si può omettere" }));
    expect(screen.queryByRole("textbox", { name: "Nota per riso" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(save).toHaveBeenCalledWith({ verdict: "omit", substitutes: [] });
  });

  it("la ✕ toglie un sostituto", async () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    await userEvent.click(screen.getByRole("button", { name: "Togli riso" }));
    expect(screen.queryByRole("textbox", { name: "Nota per riso" })).toBeNull();
    expect(screen.getByRole("button", { name: "Salva per questa ricetta" })).toHaveAttribute(
      "aria-disabled", "true"
    );
  });

  it("il rifiuto del server si legge com'è", async () => {
    const frase = "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente.";
    renderEditor({
      initialVerdict: "substitutes", initialSubstitutes: [RISO],
      save: vi.fn(async () => {
        throw new ApiError(frase, 422, { detail: frase });
      }),
    });
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(frase);
  });

  it("ogni altro guasto dice di riprovare", async () => {
    renderEditor({
      initialVerdict: "omit",
      save: vi.fn(async () => {
        throw new Error("rete");
      }),
    });
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a salvare. Riprova.");
  });

  it("«Annulla» chiude senza salvare", async () => {
    const { save, onCancel } = renderEditor({ initialVerdict: "omit" });
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });
});

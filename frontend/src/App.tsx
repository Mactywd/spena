import { useState } from "react";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AiDraftScreen } from "./features/ai-draft/AiDraftScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { RecipeDetailScreen } from "./features/cooking/RecipeDetailScreen";
import { PantryScreen } from "./features/pantry/PantryScreen";
import { ImportQueueScreen } from "./features/recipe-import/ImportQueueScreen";
import { RecipeBookScreen } from "./features/recipes/RecipeBookScreen";
import { ShoppingListScreen } from "./features/shopping-list/ShoppingListScreen";
import { StockingScreen } from "./features/stocking/StockingScreen";
import { TabBar } from "./components/TabBar";
import { UnauthorizedError } from "./api/client";
import { defaultQueryRetryPredicate } from "./lib/queryRetry";

export default function App() {
  const [authenticated, setAuthenticated] = useState(true);

  // creato una volta sola: ricostruirlo a ogni render svuoterebbe la cache
  const [queryClient] = useState(() => {
    // un 401 da qualsiasi chiamata riporta all'accesso, senza schermate rotte.
    // Servono entrambe le cache: le query leggono, ma spuntare una voce, cambiare
    // uno stato in dispensa e cucinare una ricetta sono mutazioni, e una sessione
    // scaduta a metà di una di quelle lascerebbe la schermata ferma su dati vecchi
    // senza dire perché.
    const bounceToLogin = (error: unknown) => {
      if (error instanceof UnauthorizedError) setAuthenticated(false);
    };

    return new QueryClient({
      queryCache: new QueryCache({ onError: bounceToLogin }),
      mutationCache: new MutationCache({ onError: bounceToLogin }),
      defaultOptions: {
        queries: {
          retry: defaultQueryRetryPredicate,
        },
      },
    });
  });

  if (!authenticated) return <LoginScreen onSuccess={() => setAuthenticated(true)} />;

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* max-w-md: l'app è pensata per un telefono, e su uno schermo largo una
            lista che attraversa 1400px non si legge. pb-24 tiene l'ultima riga
            sopra la barra delle schede, che è fissa e coprirebbe un bersaglio. */}
        <main className="mx-auto min-h-dvh max-w-md pb-24">
          <Routes>
            <Route path="/" element={<Navigate to="/lista" replace />} />
            <Route path="/lista" element={<ShoppingListScreen />} />
            <Route path="/sistema" element={<StockingScreen />} />
            <Route path="/dispensa" element={<PantryScreen />} />
            <Route path="/ricette" element={<RecipeBookScreen />} />
            {/* dichiarata SOPRA /ricette/:id: "nuova-ai" non deve mai essere
                letto come un id di ricetta. */}
            <Route path="/ricette/nuova-ai" element={<AiDraftScreen />} />
            {/* dichiarata SOPRA /ricette/:id, per lo stesso motivo: "importa" non
                deve mai essere letto come un id di ricetta. */}
            <Route path="/ricette/importa" element={<ImportQueueScreen />} />
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
          </Routes>
        </main>
        <TabBar />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

import { useState } from "react";
import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LoginScreen } from "./features/auth/LoginScreen";
import { RecipeDetailScreen } from "./features/cooking/RecipeDetailScreen";
import { PantryScreen } from "./features/pantry/PantryScreen";
import { RecipeBookScreen } from "./features/recipes/RecipeBookScreen";
import { ShoppingListScreen } from "./features/shopping-list/ShoppingListScreen";
import { StockingScreen } from "./features/stocking/StockingScreen";
import { TabBar } from "./components/TabBar";
import { UnauthorizedError } from "./api/client";

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
        queries: { retry: (_count, error) => !(error instanceof UnauthorizedError) },
      },
    });
  });

  if (!authenticated) return <LoginScreen onSuccess={() => setAuthenticated(true)} />;

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <main className="min-h-dvh pb-20">
          <Routes>
            <Route path="/" element={<Navigate to="/lista" replace />} />
            <Route path="/lista" element={<ShoppingListScreen />} />
            <Route path="/sistema" element={<StockingScreen />} />
            <Route path="/dispensa" element={<PantryScreen />} />
            <Route path="/ricette" element={<RecipeBookScreen />} />
            {/* Task 23 aggiungerà /ricette/nuova-ai: va dichiarata SOPRA questa,
                perché "nuova-ai" non deve mai essere letto come un :id. */}
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
          </Routes>
        </main>
        <TabBar />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

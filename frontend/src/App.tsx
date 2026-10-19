import { useState } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AiDraftScreen } from "./features/ai-draft/AiDraftScreen";
import { LoginScreen } from "./features/auth/LoginScreen";
import { RecipeDetailScreen } from "./features/cooking/RecipeDetailScreen";
import { PantryScreen } from "./features/pantry/PantryScreen";
import { ImportQueueScreen } from "./features/recipe-import/ImportQueueScreen";
import { RecipeVariantScreen } from "./features/ai-variant/RecipeVariantScreen";
import { RecipeEditScreen } from "./features/recipe-form/RecipeEditScreen";
import { RecipeBookScreen } from "./features/recipes/RecipeBookScreen";
import { NotFoundScreen } from "./features/not-found/NotFoundScreen";
import { IngredientScreen } from "./features/registry/IngredientScreen";
import { ProductScreen } from "./features/registry/ProductScreen";
import { RegistryScreen } from "./features/registry/RegistryScreen";
import { ShoppingListScreen } from "./features/shopping-list/ShoppingListScreen";
import { StockingScreen } from "./features/stocking/StockingScreen";
import { ActivityScreen } from "./features/activity/ActivityScreen";
import { ConnectScreen } from "./features/activity/ConnectScreen";
import { SpendingScreen } from "./features/spending/SpendingScreen";
import { AppHeader } from "./components/AppHeader";
import { TabBar } from "./components/TabBar";
import { NoticeProvider } from "./components/ui/NoticeProvider";
import { createAppQueryClient } from "./lib/queryClient";

export default function App() {
  const [authenticated, setAuthenticated] = useState(true);

  // creato una volta sola: ricostruirlo a ogni render svuoterebbe la cache. Com'è fatto
  // (i 401 che riportano all'accesso, i tentativi) sta in lib/queryClient.ts, dove lo
  // prendono anche i test
  const [queryClient] = useState(() => createAppQueryClient(() => setAuthenticated(false)));

  if (!authenticated) return <LoginScreen onSuccess={() => setAuthenticated(true)} />;

  return (
    <QueryClientProvider client={queryClient}>
      <NoticeProvider>
        <BrowserRouter>
          <AppHeader />
          {/* max-w-md: l'app è pensata per un telefono, e su uno schermo largo una
              lista che attraversa 1400px non si legge. pb-24 tiene l'ultima riga
              sopra la barra delle schede, che è fissa e coprirebbe un bersaglio.
              L'altezza minima toglie i 3rem dell'intestazione: con `min-h-dvh`
              pieno la pagina sarebbe sempre più alta dello schermo di quei 3rem,
              e ogni schermata avrebbe una barra di scorrimento che non serve. */}
          <main className="mx-auto min-h-[calc(100dvh-3rem)] max-w-md pb-24">
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
              <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
              <Route path="/ricette/:id/variante" element={<RecipeVariantScreen />} />
              <Route path="/anagrafica" element={<RegistryScreen />} />
              <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
              <Route path="/anagrafica/prodotto/:id" element={<ProductScreen />} />
              <Route path="/attivita" element={<ActivityScreen />} />
              <Route path="/attivita/collega" element={<ConnectScreen />} />
              <Route path="/spese-ai" element={<SpendingScreen />} />
              {/* in fondo: prende solo ciò che nessuna rotta sopra ha preso */}
              <Route path="*" element={<NotFoundScreen />} />
            </Routes>
          </main>
          <TabBar />
        </BrowserRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

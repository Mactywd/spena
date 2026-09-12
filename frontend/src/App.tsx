import { useState } from "react";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { LoginScreen } from "./features/auth/LoginScreen";
import { TabBar } from "./components/TabBar";
import { UnauthorizedError } from "./api/client";

export default function App() {
  const [authenticated, setAuthenticated] = useState(true);

  // creato una volta sola: ricostruirlo a ogni render svuoterebbe la cache
  const [queryClient] = useState(
    () =>
      new QueryClient({
        // un 401 da qualsiasi chiamata riporta all'accesso, senza schermate rotte
        queryCache: new QueryCache({
          onError: (error) => {
            if (error instanceof UnauthorizedError) setAuthenticated(false);
          },
        }),
        defaultOptions: {
          queries: { retry: (_count, error) => !(error instanceof UnauthorizedError) },
        },
      })
  );

  if (!authenticated) return <LoginScreen onSuccess={() => setAuthenticated(true)} />;

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <main className="min-h-dvh pb-20">
          <Routes>
            <Route path="/" element={<Navigate to="/lista" replace />} />
            <Route path="/lista" element={<div className="p-4">Lista</div>} />
            <Route path="/dispensa" element={<div className="p-4">Dispensa</div>} />
            <Route path="/ricette" element={<div className="p-4">Ricette</div>} />
          </Routes>
        </main>
        <TabBar />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

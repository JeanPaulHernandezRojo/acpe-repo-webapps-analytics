import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { ProtectedLayout } from "@/components/layout/ProtectedLayout";
import { ConfigProvider } from "@/components/ConfigProvider";
import { CompleteLoginPage } from "@/pages/CompleteLoginPage";
import { LoginPage } from "@/pages/LoginPage";
import { NoToolsPage } from "@/pages/NoToolsPage";
import { ToolsPage } from "@/pages/ToolsPage";
import { ViewerPage } from "@/pages/ViewerPage";

/** Rutas del portal. Las del layout protegido exigen sesión (ver ProtectedLayout). */

export function App() {
  return (
    <ConfigProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/ingreso" element={<LoginPage />} />
          <Route path="/ingreso/completar" element={<CompleteLoginPage />} />
          <Route path="/sin-herramientas" element={<NoToolsPage />} />
          <Route element={<ProtectedLayout />}>
            <Route index element={<ToolsPage />} />
            <Route path="herramientas/:dominio/:appId" element={<ViewerPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}

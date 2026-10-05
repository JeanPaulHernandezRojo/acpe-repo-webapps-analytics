import type { ReactNode } from "react";

/** Pantalla centrada para estados de carga, error o páginas estáticas. */

interface FullScreenMessageProps {
  title: string;
  message: string;
  children?: ReactNode;
}

export function FullScreenMessage({ title, message, children }: FullScreenMessageProps) {
  return (
    <main className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-md rounded-xl border border-[#E5E7EB] bg-white p-8 text-center shadow-sm">
        <img src="/logo.svg" alt="" className="mx-auto mb-5 size-12" />
        <h1 className="font-display text-xl font-bold text-[#1A1A1A]">{title}</h1>
        {message && <p className="mt-2 text-[0.95rem] text-secondary-400">{message}</p>}
        {children && <div className="mt-6">{children}</div>}
      </div>
    </main>
  );
}

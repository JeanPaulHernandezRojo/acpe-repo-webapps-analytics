import { MailCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router";
import { BrandMark } from "@/components/BrandMark";
import { Button } from "@/components/ui/button";
import { useConfig } from "@/context/ConfigContext";
import { reportLoginEvent } from "@/lib/api";
import { evaluateEmail } from "@/lib/emailPolicy";
import { getAuthClient, sendAccessLink } from "@/lib/identity";
import { maskEmail } from "@/lib/utils";

/** Ingreso: el usuario escribe su correo y recibe un enlace de acceso de un solo uso. */

export function LoginPage() {
  const config = useConfig();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const expired = params.get("motivo") === "sesion_expirada";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const result = evaluateEmail(email, config.politica);
    if (!result.allowed) {
      setError(
        result.reason === "formato_invalido"
          ? "Escribe un correo válido."
          : config.politica.mensaje_rechazo,
      );
      if (result.reason !== "formato_invalido") {
        void reportLoginEvent("enlace_rechazado_politica", result.email).catch(() => undefined);
      }
      return;
    }
    setSending(true);
    try {
      await sendAccessLink(getAuthClient(config.identidad), result.email);
      void reportLoginEvent("enlace_solicitado", result.email).catch(() => undefined);
      setSentTo(result.email);
    } catch {
      setError("No pudimos enviar el enlace. Inténtalo nuevamente en unos minutos.");
    } finally {
      setSending(false);
    }
  };

  return (
    <main className="flex min-h-full items-center justify-center px-4 py-12">
      <div className="w-full max-w-md rounded-xl border border-[#E5E7EB] bg-white p-8 shadow-sm">
        <BrandMark
          name={config.portal.nombre}
          subtitle={config.portal.subtitulo}
          compact={false}
          className="mb-8"
        />

        {sentTo ? (
          <div className="text-center">
            <MailCheck className="mx-auto mb-4 size-10 text-primary-500" strokeWidth={1.5} />
            <h1 className="font-display text-xl font-bold text-[#1A1A1A]">Revisa tu correo</h1>
            <p className="mt-2 text-[0.95rem] text-secondary-400">
              Te enviamos un enlace de acceso a <strong>{maskEmail(sentTo)}</strong>. Ábrelo en este
              mismo navegador. El enlace es personal: no lo reenvíes.
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-6"
              onClick={() => {
                setSentTo(null);
                setEmail("");
              }}
            >
              Usar otro correo
            </Button>
          </div>
        ) : (
          <form onSubmit={submit} noValidate>
            <h1 className="font-display text-xl font-bold text-[#1A1A1A]">Ingresar</h1>
            <p className="mt-1 mb-6 text-[0.9rem] text-secondary-400">
              Escribe tu correo corporativo y te enviaremos un enlace de acceso.
            </p>
            {expired && (
              <p className="mb-4 rounded-lg bg-primary-50 px-3 py-2 text-[0.85rem] text-primary-700">
                Tu sesión expiró. Ingresa nuevamente.
              </p>
            )}
            <label htmlFor="correo" className="text-[0.85rem] font-semibold text-secondary-500">
              Correo
            </label>
            <input
              id="correo"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="usuario@alicorp.com.pe"
              className="mt-1 h-11 w-full rounded-lg border border-secondary-200 px-3 text-[0.95rem] outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
            />
            {error && <p className="mt-2 text-[0.85rem] text-primary-600">{error}</p>}
            <Button type="submit" className="mt-6 w-full" disabled={sending || !email.trim()}>
              {sending ? "Enviando…" : "Enviar enlace de acceso"}
            </Button>
          </form>
        )}
      </div>
    </main>
  );
}

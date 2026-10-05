import { FirebaseError } from "firebase/app";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { FullScreenMessage } from "@/components/FullScreenMessage";
import { Button } from "@/components/ui/button";
import { useConfig } from "@/context/ConfigContext";
import { ApiError, createSession } from "@/lib/api";
import { normalizeEmail } from "@/lib/emailPolicy";
import { completeAccessLink, getAuthClient, isAccessLink, pendingEmail } from "@/lib/identity";

/**
 * Destino del enlace de acceso: completa el ingreso con Identity Platform, crea la sesión en el
 * backend y redirige. Si el enlace se abre en otro navegador, pide confirmar el correo.
 */

type Phase = { step: "working" } | { step: "askEmail" } | { step: "error"; message: string };

function failureMessage(error: unknown, rejection: string): string {
  if (error instanceof ApiError && error.status === 403) return error.detail || rejection;
  if (error instanceof FirebaseError) {
    if (error.code === "auth/invalid-action-code" || error.code === "auth/expired-action-code") {
      return "El enlace venció o ya fue usado. Solicita uno nuevo.";
    }
    if (error.code === "auth/invalid-email") {
      return "El correo no coincide con el enlace. Solicita uno nuevo.";
    }
  }
  return "No pudimos completar el ingreso. Solicita un nuevo enlace.";
}

export function CompleteLoginPage() {
  const config = useConfig();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<Phase>({ step: "working" });
  const [email, setEmail] = useState("");
  const started = useRef(false);

  const finish = useCallback(
    async (address: string) => {
      setPhase({ step: "working" });
      try {
        const auth = getAuthClient(config.identidad);
        const idToken = await completeAccessLink(auth, address, window.location.href);
        const { tiene_apps } = await createSession(idToken);
        navigate(tiene_apps ? "/" : "/sin-herramientas", { replace: true });
      } catch (error) {
        setPhase({
          step: "error",
          message: failureMessage(error, config.politica.mensaje_rechazo),
        });
      }
    },
    [config, navigate],
  );

  useEffect(() => {
    // Evita el doble intento del modo estricto de React: el enlace es de un solo uso.
    if (started.current) return;
    started.current = true;
    const auth = getAuthClient(config.identidad);
    if (!isAccessLink(auth, window.location.href)) {
      setPhase({ step: "error", message: "El enlace no es válido. Solicita uno nuevo." });
      return;
    }
    const stored = pendingEmail();
    if (stored) {
      void finish(stored);
    } else {
      setPhase({ step: "askEmail" });
    }
  }, [config, finish]);

  if (phase.step === "working") {
    return (
      <FullScreenMessage title="Ingresando…" message="Estamos validando tu enlace de acceso." />
    );
  }

  if (phase.step === "error") {
    return (
      <FullScreenMessage title="No pudimos completar el ingreso" message={phase.message}>
        <Link to="/ingreso" className="font-semibold text-primary-600 hover:underline">
          Volver al ingreso
        </Link>
      </FullScreenMessage>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void finish(normalizeEmail(email));
  };

  return (
    <FullScreenMessage
      title="Confirma tu correo"
      message="Abriste el enlace en un navegador distinto. Escribe el correo al que llegó el enlace."
    >
      <form onSubmit={submit} className="text-left">
        <input
          type="email"
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="usuario@alicorp.com.pe"
          className="h-11 w-full rounded-lg border border-secondary-200 px-3 text-[0.95rem] outline-none focus:border-primary-400 focus:ring-2 focus:ring-primary-100"
        />
        <Button type="submit" className="mt-4 w-full" disabled={!email.trim()}>
          Continuar
        </Button>
      </form>
    </FullScreenMessage>
  );
}

import { initializeApp, getApps, type FirebaseApp } from "firebase/app";
import {
  initializeAuth,
  inMemoryPersistence,
  isSignInWithEmailLink,
  sendSignInLinkToEmail,
  signInWithEmailLink,
  signOut,
  type Auth,
} from "firebase/auth";
import type { PublicConfig } from "@/types";
import { readLocal, removeLocal, writeLocal } from "@/lib/storage";

/**
 * Ingreso con enlace de acceso (Identity Platform). El SDK trabaja en memoria: no guarda tokens
 * en el navegador. El ID token solo se usa una vez para crear la cookie de sesión del backend.
 */

const FIREBASE_APP_NAME = "alejandria";

/** Correo pendiente entre el envío del enlace y su apertura (mismo navegador). */
const PENDING_EMAIL_KEY = "alejandria_correo_ingreso";

/** Ruta del portal a la que vuelve el enlace de acceso. */
export const COMPLETE_PATH = "/ingreso/completar";

let authClient: Auth | null = null;

export function getAuthClient(identity: PublicConfig["identidad"]): Auth {
  if (authClient) return authClient;
  const existing = getApps().find((app) => app.name === FIREBASE_APP_NAME);
  const app: FirebaseApp =
    existing ??
    initializeApp(
      { apiKey: identity.api_key, authDomain: identity.auth_domain },
      FIREBASE_APP_NAME,
    );
  authClient = initializeAuth(app, { persistence: inMemoryPersistence });
  return authClient;
}

export async function sendAccessLink(auth: Auth, email: string): Promise<void> {
  await sendSignInLinkToEmail(auth, email, {
    url: `${window.location.origin}${COMPLETE_PATH}`,
    handleCodeInApp: true,
  });
  writeLocal(PENDING_EMAIL_KEY, email);
}

export function isAccessLink(auth: Auth, href: string): boolean {
  return isSignInWithEmailLink(auth, href);
}

export function pendingEmail(): string | null {
  return readLocal(PENDING_EMAIL_KEY);
}

/** Completa el enlace y devuelve el ID token. Deja el SDK sin usuario al terminar. */
export async function completeAccessLink(auth: Auth, email: string, href: string): Promise<string> {
  const credential = await signInWithEmailLink(auth, email, href);
  try {
    return await credential.user.getIdToken();
  } finally {
    await signOut(auth);
    removeLocal(PENDING_EMAIL_KEY);
  }
}

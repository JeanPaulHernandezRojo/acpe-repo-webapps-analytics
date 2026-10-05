/**
 * Acceso tolerante a localStorage: en ventanas privadas o con almacenamiento bloqueado puede
 * fallar, y el portal debe seguir funcionando (solo se pierde la conveniencia).
 */

export function readLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeLocal(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Sin almacenamiento disponible: se ignora.
  }
}

export function removeLocal(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Sin almacenamiento disponible: se ignora.
  }
}

/** Contratos de datos entre el frontend y el backend (ver portal/backend/src/alejandria/routes.py). */

export interface PublicConfig {
  portal: {
    nombre: string;
    subtitulo: string;
    contacto: string;
    version: string;
  };
  politica: EmailPolicyRules;
  identidad: {
    api_key: string;
    auth_domain: string;
  };
  latido_segundos: number;
  ambiente: string;
}

export interface EmailPolicyRules {
  dominios_permitidos: string[];
  prefijos_excluidos: string[];
  mensaje_rechazo: string;
}

export interface Capabilities {
  descargas: boolean;
  ventanas: boolean;
  dialogos: boolean;
  formularios: boolean;
}

export type WatermarkLevel = "patron_suave" | "esquina" | "franja" | "patron";

export interface AppSummary {
  id: string;
  dominio: string;
  version: string;
  titulo: string;
  descripcion: string;
  icono: string;
  etiqueta: string;
  capacidades: Capabilities;
  marca_agua: WatermarkLevel;
}

export interface Me {
  correo: string;
  apps: AppSummary[];
}

export type LoginEventType = "enlace_solicitado" | "enlace_rechazado_politica";

export interface ViewerEvent {
  tipo: "app_abierta" | "latido" | "app_cerrada";
  dominio: string;
  app_id: string;
  tiempo_carga_ms: number | null;
  duracion_s: number | null;
  generacion_html: string | null;
}

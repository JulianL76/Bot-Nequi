/**
 * Mapa de navegación.
 *
 * Las URLs vienen de Django (props compartidas): aquí solo se les pone icono,
 * etiqueta y grupo. Así un cambio en `urls.py` nunca deja un enlace roto en el
 * front, y el front nunca escribe una ruta a mano.
 */
import {
  ArrowLeftRight, Bell, Banknote, ChartColumn, CloudUpload, Hourglass,
  LayoutDashboard, ListChecks, Loader, Package, ReceiptText, Route, Settings, Upload,
} from 'lucide-react';

/** Definición estática: clave de URL -> cómo se presenta. */
const ITEMS = [
  { clave: 'inicio',         label: 'Dashboard',      grupo: 'Operación',     icon: LayoutDashboard, componente: 'Dashboard/Home' },
  { clave: 'pendientes',     label: 'Pendientes',     grupo: 'Operación',     icon: Hourglass,       componente: 'Dashboard/Pendientes' },
  { clave: 'comprobantes',   label: 'Comprobantes',   grupo: 'Comprobantes',  icon: ReceiptText,     componente: 'Comprobantes/Lista', tambien: ['Comprobantes/Editar'] },
  { clave: 'subir',          label: 'Subir',          grupo: 'Comprobantes',  icon: CloudUpload,     componente: 'Comprobantes/Subir' },
  { clave: 'subidas',        label: 'Subidas',        grupo: 'Comprobantes',  icon: Package,         componente: 'Comprobantes/Lotes', tambien: ['Comprobantes/LoteDetalle'] },
  { clave: 'enProceso',      label: 'En proceso',     grupo: 'Comprobantes',  icon: Loader,          componente: 'Comprobantes/EnProceso' },
  { clave: 'importar',       label: 'Importar',       grupo: 'Comprobantes',  icon: Upload,          componente: 'Comprobantes/Importar', soloPaleta: true },
  { clave: 'conciliar',      label: 'Conciliar',      grupo: 'Conciliación',  icon: ArrowLeftRight,  componente: 'Conciliaciones/Conciliar' },
  { clave: 'conciliaciones', label: 'Conciliaciones', grupo: 'Conciliación',  icon: ListChecks,      componente: 'Conciliaciones/Lista', tambien: ['Conciliaciones/LoteDetalle', 'Conciliaciones/Ajustar'] },
  { clave: 'panel',          label: 'Panel',          grupo: 'Conciliación',  icon: ChartColumn,     componente: 'Conciliaciones/Panel' },
  { clave: 'rutas',          label: 'Rutas',          grupo: 'Configuración', icon: Route,           componente: 'Comprobantes/Rutas' },
  { clave: 'notificaciones', label: 'Notificaciones', grupo: 'Configuración', icon: Bell,            componente: 'Comprobantes/Notificaciones', avisos: true },
  { clave: 'admin',          label: 'Administración', grupo: 'Configuración', icon: Settings,        externo: true },
];

/** Pestañas de la barra inferior en móvil, en orden. */
const TABS = ['inicio', 'comprobantes', 'subir', 'pendientes'];

export const MARCA_ICON = Banknote;

/** Construye la navegación resolviendo cada clave con las URLs de Django. */
export function construirRutas(urls = {}) {
  return ITEMS.filter((i) => urls[i.clave]).map((i) => ({ ...i, url: urls[i.clave] }));
}

/** Solo lo que va en el menú lateral, ya agrupado. */
export function rutasAgrupadas(urls) {
  const items = construirRutas(urls).filter((i) => !i.soloPaleta);
  const grupos = [];
  for (const item of items) {
    let g = grupos.find((x) => x.nombre === item.grupo);
    if (!g) grupos.push((g = { nombre: item.grupo, items: [] }));
    g.items.push(item);
  }
  return grupos;
}

export function rutasTabs(urls) {
  const items = construirRutas(urls);
  return TABS.map((c) => items.find((i) => i.clave === c)).filter(Boolean);
}

/** ¿Este ítem corresponde al componente que se está mostrando? */
export function estaActivo(item, componente) {
  return item.componente === componente || item.tambien?.includes(componente);
}

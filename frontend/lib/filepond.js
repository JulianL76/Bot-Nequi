/**
 * Carga del motor de subida (FilePond) bajo demanda.
 *
 * El motor es JavaScript clásico que manipula el DOM directamente y está muy
 * afinado para el caso real —cientos de fotos desde un celular con red mala,
 * una petición por imagen, con reintentos—, así que NO se reescribió en React:
 * reescribirlo sería cambiar código probado por código nuevo sin ganar nada.
 *
 * Lo que sí cambia: se carga solo en la pantalla que lo usa, en vez de ir en
 * todas las páginas.
 */

const ASSETS = [
  '/static/vendor/filepond/filepond-plugin-file-validate-type.min.js',
  '/static/vendor/filepond/filepond-plugin-file-validate-size.min.js',
  '/static/vendor/filepond/filepond.min.js',
  '/static/vendor/filepond/motor-subida.js',
];

const CSS = '/static/vendor/filepond/filepond.min.css';

let promesa = null;

function cargarScript(src) {
  return new Promise((resolve, reject) => {
    // Los scripts se cachean por src: volver a la pantalla no los recarga.
    const existente = document.querySelector(`script[data-fp="${src}"]`);
    if (existente) { resolve(); return; }

    const el = document.createElement('script');
    el.src = src;
    el.dataset.fp = src;
    el.onload = resolve;
    el.onerror = () => reject(new Error(`No se pudo cargar ${src}`));
    document.head.appendChild(el);
  });
}

/** Carga CSS y scripts en orden (los plugins deben existir antes que FilePond). */
export function cargarFilePond() {
  if (promesa) return promesa;

  if (!document.querySelector(`link[data-fp="${CSS}"]`)) {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = CSS;
    link.dataset.fp = CSS;
    document.head.appendChild(link);
  }

  promesa = ASSETS.reduce((cadena, src) => cadena.then(() => cargarScript(src)), Promise.resolve());
  return promesa;
}

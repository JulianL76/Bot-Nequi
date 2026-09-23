/**
 * Token CSRF para las peticiones que NO pasan por Inertia.
 *
 * Inertia manda la cabecera X-XSRF-TOKEN solo, pero la subida de imágenes usa
 * `fetch` y un formulario clásico (el motor de FilePond), así que necesita el
 * token a mano. La cookie no es HttpOnly, por eso se puede leer aquí.
 */
export function csrfToken() {
  const par = document.cookie
    .split('; ')
    .find((c) => c.startsWith('csrftoken='));
  return par ? decodeURIComponent(par.slice('csrftoken='.length)) : '';
}

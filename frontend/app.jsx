/**
 * Punto de entrada de la aplicación React.
 *
 * Inertia mantiene montado el armazón entre páginas: Django devuelve props en
 * vez de HTML y aquí solo se intercambia el componente de página. Por eso no
 * hay recarga ni parpadeo, y el estado del armazón (scroll del menú, toasts,
 * tema) sobrevive a la navegación.
 */
import './styles/app.css';

import { createInertiaApp } from '@inertiajs/react';
import { createRoot } from 'react-dom/client';
import Layout from './Layout.jsx';

createInertiaApp({
  // CSRF. Inertia viene con la convención de Laravel: lee la cookie
  // `XSRF-TOKEN` y manda la cabecera `X-XSRF-TOKEN`. Django usa `csrftoken` y
  // espera `X-CSRFToken`, así que sin esto NINGÚN router.post/delete lleva
  // token y Django los rechaza con 403 "CSRF token missing".
  //
  // Se ajusta Inertia y no Django a propósito: renombrar la cookie en settings
  // también valdría, pero rompería `lib/csrf.js`, que la lee por su nombre
  // para las subidas con fetch y FilePond.
  http: { xsrfCookieName: 'csrftoken', xsrfHeaderName: 'X-CSRFToken' },

  // El nombre que manda Django ("Comprobantes/Lista") es la ruta del archivo.
  //
  // El glob NO es `eager`: cada página queda en su propio trozo y se descarga
  // al visitarla. Importa: ApexCharts pesa más que el resto del armazón junto,
  // y solo hace falta en el dashboard.
  resolve: async (nombre) => {
    const paginas = import.meta.glob('./Pages/**/*.jsx');
    const cargar = paginas[`./Pages/${nombre}.jsx`];
    if (!cargar) throw new Error(`No existe la página ${nombre}`);

    const pagina = await cargar();
    // Layout por defecto; una página puede fijar el suyo con `Pagina.layout`.
    pagina.default.layout ??= (contenido) => <Layout>{contenido}</Layout>;
    return pagina;
  },

  setup({ el, App, props }) {
    createRoot(el).render(<App {...props} />);
  },

  // Barra de progreso de Inertia con el color de la marca. `delay` evita que
  // parpadee en las respuestas rápidas, que son la mayoría.
  progress: {
    color: '#3b45e0',
    delay: 180,
    showSpinner: false,
  },
});

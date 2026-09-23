# Design system — Gestor Nequi

Marca nueva (2026-09). Sustituye al esquema violeta/slate anterior.

La fuente de verdad es **`frontend/styles/tokens.css`**: si un color, radio o
sombra no sale de ahí, está mal. En las plantillas no se escriben hex sueltos.

## Color

| Rol | Token | Por qué |
|---|---|---|
| Marca | `brand-*` (cobalto, `600 = #3b45e0`) | Serio y financiero. Deja libres verde/ámbar/rojo para los estados, cosa que el violeta anterior no permitía sin ambigüedad. |
| Neutros | `ink-*` | Grises levemente fríos, para que las tablas densas no cansen la vista. |
| Acento | `accent-*` (ámbar) | Destacados puntuales y series de gráficas. |
| Éxito / alerta / error | `ok-*`, `warn-*`, `bad-*` | Significado fijo: nunca se usan como decoración. |

### Superficies semánticas

En lugar de repetir `bg-white dark:bg-slate-800` en cada plantilla, se usan
tokens que ya saben cambiar de tema:

`bg-surface` · `bg-surface-sunken` (fondo de la app) · `bg-surface-raised`
(popovers y hojas) · `bg-surface-inset` (celdas, inputs) · `bg-surface-hover`
`border-line` · `border-line-strong`
`text-content` · `text-muted` · `text-subtle`
`bg-shell` (la barra lateral, oscura en ambos temas)

El modo oscuro se activa con la clase `.dark` en `<html>`, que escribe el script
del `<head>` antes del primer pintado.

## Tipografía

- Títulos: **Plus Jakarta Sans** (`font-display`)
- Interfaz: **Inter** (`font-sans`)
- Referencias y montos: **JetBrains Mono** (`font-mono`)

Self-hosted vía `@fontsource-variable` (solo subset latino).

### Roles tipográficos

Antes había **nueve** tamaños sueltos (9, 10, 11, 12, 13, 14, 16, 18, 20 px) sin
sistema detrás, y dos de ellos —13 semibold y 12 medium— tan parecidos que no
podían cargar trabajos distintos: todo pesaba igual y la jerarquía no existía.

Ahora son **seis roles con nombre**. Cada salto combina tamaño **y** peso **y**
color, no tamaño a secas, para que se distingan sin leer el texto:

| Rol | Tamaño | Peso | Color | Para qué |
|---|---|---|---|---|
| `t-titulo` | 18 | 700 | contenido | el título de la pantalla; uno por vista |
| `t-dato` | 15 | 700 | contenido | la cifra que se viene a ver (tabular) |
| `t-seccion` | 13 | 600 | contenido | cabeceras de tarjeta y de bloque |
| `t-cuerpo` | 13 | 400 | contenido | texto normal y celdas de tabla |
| `t-meta` | 11 | 400 | atenuado | fecha, referencia, autoría, pie |
| `t-micro` | 10 | 700 | sutil | badges y antetítulos, en versalitas |

Al escribir una pantalla nueva se elige el rol por su **papel**, no por cómo se
ve. Si hace falta un tamaño que no está en la tabla, casi siempre sobra un rol.

**Se pueden sobrescribir**: `t-meta text-warn-600` sale ámbar y `t-dato text-lg`
sale a 18 px, porque Tailwind emite las utilidades generadas después de las
propias. Sirve para las excepciones, no para saltarse la escala.

**Dos ámbitos NO siguen estos roles, a propósito:**

- **La navegación** tiene su escala, más holgada (`--h-nav-item`, texto de 14):
  son pocos elementos, se tocan con el dedo y apretarlos no gana nada.
- **Los controles** (botones, chips, campos) se dimensionan con `--h-control` y
  su propio tamaño de texto: son cromo, no contenido.

Toda cifra en tabla lleva `tabular-nums` (`th`, `td` y `.nums`). Las cifras
grandes y sueltas —`t-dato`, `t-titulo`— usan figuras proporcionales: a ese
tamaño, `tabular-nums` le da a cada dígito el ancho de un cero y se ve suelto.

### Jerarquía en una fila de datos

El ejemplo canónico es el ítem de conciliación. El orden de lectura debe seguir
al de importancia real al conciliar, no al orden en que están los campos:

```
$ 61.000,00   ● OK              ← t-dato + estado: cuánto y cómo salió
M20139453 · Karen Acuna         ← t-cuerpo: cuál es y de quién
01 de julio de 2026 · 16:45     ← t-meta: el contexto, claramente debajo
```

## Componentes

Dos capas que se complementan:

- **CSS** (`frontend/styles/app.css`): la apariencia. Son clases sueltas que
  cualquier elemento puede usar.
- **React** (`frontend/ui/`): la API tipada y lo que CSS no puede hacer — foco
  atrapado en los diálogos, estado de carga, semántica ARIA. Los primitivos
  accesibles son de **Radix**; Base UI sería la opción preferida por la guía
  pero sigue en release candidate y esto es una app en uso.

- Botones: `.btn-primary` `.btn-secondary` `.btn-ghost` `.btn-danger`
  `.btn-success`, con los modificadores `.btn-sm` `.btn-lg` `.btn-icon`
- Superficies: `.card` `.card-pad` `.card-header` `.card-title`
- Formularios: `.field` `.label` `.hint` `.error-text`
- Estado: `.badge-ok` `.badge-warn` `.badge-bad` `.badge-brand` `.badge-neutral`,
  más `.dot` para el punto de color de las tablas
- Datos: `.table-wrap` + `.table`
- Vacíos y carga: `.empty-state` `.skeleton`

Del kit de React salen `Button`, `Card`, `Badge`, `Input`, `Select`, `Campo`,
`Switch`, `Checkbox`, `Dialog`, `ConfirmDialog`, `EmptyState`, `Skeleton` y
`Progress`.

`SelectorFecha` y `SelectorHora` (en `components/`) sustituyen a
`<input type="date">` y `<input type="time">`. El nativo se pintaba invisible
bajo su etiqueta y Chrome solo abre su selector al pulsar el icono del
calendario, que así no se veía: el filtro no llegaba a abrirse nunca. El
calendario es **react-day-picker** en español dentro de un popover de Radix, y
la hora son dos columnas desplazables. Cuesta ~12 kB comprimidos en el trozo de
la lista de comprobantes, no en el armazón.

`Select` va sobre Radix, no sobre `<select>` nativo: la lista desplegable de un
select nativo la pinta el sistema operativo y no hereda ni el tema oscuro ni la
tipografía. Mantiene la API del nativo —recibe `<option>` y avisa con
`onChange({ target: { value } })`— así que se usa igual. Dos detalles internos:
una opción con `value=""` («Sin ruta», «Orden original») se traduce a un
centinela porque Radix reserva la cadena vacía, y cuando se le pasa `name`
emite un `<input type="hidden">`, ya que su disparador es un `<button>` y no
viajaría en un envío nativo.

## Movimiento

`--ease-out-soft` para entradas, `--ease-in-quick` para salidas (siempre más
cortas que las entradas) y `--ease-spring` para lo que debe sentirse físico. Todo se anula bajo
`prefers-reduced-motion` —incluidos los retrasos y las iteraciones infinitas, o
una entrada escalonada dejaría el contenido invisible durante su retraso.

Cuatro piezas de movimiento, todas por debajo de 200 ms y solo sobre `opacity` y
`transform`:

| Clase | Dónde | Qué hace y por qué |
|---|---|---|
| `.rise` | el contenedor de página, con `key` del componente | Entrada tras navegar. El `key` fuerza el remontaje; sin él solo correría la primera vez. |
| `.rise-lista` | rejilla de fichas, listas de tarjetas | Entrada escalonada de 30 ms. El retraso se corta en el octavo hijo: más allá ya no se lee como secuencia, solo como lentitud. **No se usa en tablas**, que pueden traer 1000 filas. |
| `.dot-vivo` / `.badge-vivo` | punto de estado de un proceso en curso | Halo que sale del punto y se desvanece, *detrás* de él. Dice "sigue vivo" sin apagar el dato, que es lo que hace un parpadeo de opacidad. |
| `.barra-viva` | relleno de `<Progress activo>` | Brillo que recorre la barra. Distingue "avanzando despacio" de "colgado", que con la barra quieta se ven igual. |

El movimiento aquí es información, no adorno: cada una de estas cuatro responde
a una pregunta que el usuario se estaba haciendo.

La barra de acciones en lote sale de `components/BarraAcciones.jsx` y no se
escribe a mano en cada pantalla: un `{seleccion > 0 && <div>}` desmonta el nodo
en el mismo fotograma y hace imposible cualquier animación de salida.

**Trampa al animar algo centrado con `-translate-x-1/2`:** Tailwind v4 resuelve
esa utilidad con la propiedad `translate`, no con `transform`, y las dos se
**componen**. Un fotograma que use `transform: translate(-50%, …)` desplaza el
elemento un ancho entero y lo hace saltar a su sitio al terminar. Los keyframes
de lo centrado —`entrar-barra`, `salir-barra`, `entrar-modal`, `salir-modal`—
animan `translate` (y `scale` aparte) por eso.

La navegación no bloquea la pantalla: Inertia pinta una barra de progreso
superior, con 180 ms de retraso para que no parpadee en las respuestas rápidas
(que son la mayoría). El armazón no se desmonta al cambiar de página.

## Gráficas

Escritas en SVG a mano (`frontend/components/Grafica.jsx`), no con una librería:
las dos formas que hacen falta ocupan ~5 kB frente a los 287 kB comprimidos de
ApexCharts, y el dashboard es la primera pantalla tras entrar.

Reglas que se siguen y por qué:

- **Un solo tono por gráfica.** Son magnitudes, no identidades. Con una serie
  no hay leyenda: el título la nombra.
- **Los estados no se grafican por color.** El validador de paletas marca que
  ámbar y rojo contiguos fallan el umbral de visión normal (ΔE 14.4 < 15), así
  que la distribución por estado va en fichas con etiqueta, no en una torta.
- **Un solo eje.** Montos y conteos nunca comparten gráfica.
- Marcas finas (línea de 2px), rejilla recesiva, etiquetas directas en el
  ranking y crosshair con tooltip en la serie temporal.

## Atajos

- `Ctrl/⌘ + K` o `/` abren la paleta de comandos (navegación por teclado).
- En la lista de comprobantes, `Shift + clic` selecciona un rango de filas.

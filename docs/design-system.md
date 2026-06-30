# Gestor Nequi — Design System

Base oficial del frontend (origen: artefacto de Claude Design, junio 2026).
Implementado con **Tailwind (build) + DaisyUI + HTMX + Alpine (futuro)**.

## Marca / paleta
- **Primario — Violeta:** `50 #f5f3ff · 100 #ede9fe · 200 #ddd6fe · 300 #c4b5fd · 400 #a78bfa · 500 #8b5cf6 · 600 #7c3aed (★) · 700 #6d28d9 · 800 #5b21b6 · 900 #4c1d95`
- **Semánticos:** success `#10b981` · warning `#f59e0b` · danger `#f43f5e`
- **Neutros (slate):** `50 #f8fafc … 900 #0f172a`
- **Dark mode:** clase `.dark` (Tailwind `darkMode: 'class'`); superficies slate-800/900.

## Tokens
- **Radios:** sm 6 · md 10 · lg 14 · xl 20 · full 9999
- **Espaciado (4px base):** 1=4 2=8 3=12 4=16 5=20 6=24 8=32 10=40 12=48
- **Sombras:** sm `0 1px 3px rgba(0,0,0,.06)` · md `0 4px 12px rgba(0,0,0,.08)` · lg `0 10px 30px rgba(0,0,0,.10)`
- **Tipografía:** Geist (sans) + Geist Mono (datos/refs). Números con `tabular-nums` (`.nums`).

## Escala tipográfica
Display 48/800 · H1 30/800 · H2 22/700 · H3 16/600 · Body 14/400 · Small 12/500 · Mono 13/400.

## Componentes (UI Kit)
Botones (primary/secondary/danger/ghost/icon, sm), chips/badges (verde=confirmado,
ámbar=pendiente, rosa=duplicado, violeta=en proceso, slate=bot/manual), inputs +
labels, stat cards (con sparkline), alerts (success/warning/error/info), progress
bars, tabla de datos, timeline.

## Librerías (decidido)
- **Tailwind CLI (build)** — reemplaza el CDN. *(en curso)*
- **DaisyUI** — sistema de componentes por clases, tema `nequi` (violeta/slate). *(en curso)*
- **Alpine.js** — interactividad sobre HTMX (reemplaza el JS inline en IIFE).
- **Toasts vía `HX-Trigger`** — feedback sin recargar (reemplaza banners de messages).
- **FilePond** — subida de comprobantes (preview + drag&drop).
- Flatpickr / Tom Select (con re-init en `htmx:afterSwap`) · ApexCharts (si crece el dashboard).

## Reglas del proyecto
- Todo es **hx-boost**: scripts inline en IIFE; descargas con `hx-boost="false"`;
  librerías que tocan el DOM se re-inicializan en `htmx:afterSwap`.
- Cero emojis: iconos SVG (lucide).

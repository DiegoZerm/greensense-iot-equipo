# Aplicación web

Aplicación web progresiva de GreenSense IoT, hecha con Angular 22 (componentes standalone y sin zone.js).

```bash
cd app
npm ci
npm start          # http://localhost:4200, /api se redirige al servidor en el puerto 8000
npm run demo       # http://localhost:4201, con los datos inventados de gs-demo (puerto 8001)
npm test           # pruebas con Vitest
npm run build      # build de producción en dist/
```

## Sesión y permisos

- Se entra con correo y contraseña (`/login`). El token se guarda en el navegador y viaja en cada petición a `/api`. Si el servidor lo rechaza (venció o el usuario fue desactivado), la app regresa al login.
- La barra y las rutas dependen de los permisos que el servidor devuelve para el rol: **Configuración** aparece para técnico (nodos) y administrador (cultivos, invernaderos, nodos y usuarios), y **Bitácora** para supervisor y administrador.
- El flujo en tiempo real (SSE) lleva el token en la URL, porque EventSource no permite encabezados, y se reabre solo al cambiar de sesión.
- Al salir se apagan las notificaciones de ese navegador. Si otro usuario entra en un navegador que ya estaba suscrito, la suscripción pasa a ser suya.

| Carpeta | Qué hay |
|---|---|
| `core/` | Servicios: sesión, interceptor y guards (`autenticacion.ts`), tiempo real, estado actual, alertas, push y configuración |
| `features/login`, `cuenta` | Inicio de sesión y cambio de la contraseña propia |
| `features/panel`, `alertas` | Panel en vivo con la gráfica de las últimas 6 horas, e historial de alertas con filtros por severidad, variable y fecha (con quién atendió cada una) |
| `features/configuracion` | Cultivos y umbrales, invernaderos, nodos y usuarios |
| `features/bitacora` | Registro de cambios, altas, bajas, exportaciones e inicios de sesión |
| `features/historial` | Gráficas de día (lecturas), semana (por hora), mes (por día) y rango libre (el detalle depende de su largo), filtro por variable, resumen con lecturas perdidas y exportación a CSV |
| `shared/tendencia` | Gráfica pequeña del panel: sin ejes, con la ventana, el mínimo y el máximo como texto, y el valor bajo el puntero |
| `shared/grafica-serie` | Gráfica SVG sin dependencias: línea, banda de mínimo a máximo, rango adecuado del cultivo, cortes donde faltan datos, cursor y vista en tabla |

## Historial

- El nodo, el periodo y la fecha van en la URL (`/historial?nodo=maceta1&vista=semana&fecha=2026-11-02`), así que se puede guardar o compartir la vista de un día exacto.
- Los días se cortan a medianoche hora de México (UTC-6, sin horario de verano), igual que en el servidor.
- Una gráfica por variable: no se mezclan °C y % en un mismo eje. La serie es azul (`#2a78d6`, validado contra el fondo); el rango adecuado del cultivo es una franja gris, porque el verde, amarillo y rojo quedan para las alertas.

## Íconos

Los íconos salen de `iconos/icono.svg` (esquinas redondeadas, propósito `any`) y `iconos/icono-maskable.svg` (a sangre completa, con el dibujo en el 80 % central para que Android lo recorte sin cortar la hoja). Para regenerarlos:

```bash
cd app/iconos
for t in 72 96 128 144 152 192 384 512; do rsvg-convert -w $t -h $t icono.svg -o ../public/icons/icono-$t.png; done
for t in 192 512; do rsvg-convert -w $t -h $t icono-maskable.svg -o ../public/icons/icono-maskable-$t.png; done
rsvg-convert -w 180 -h 180 icono-maskable.svg -o ../public/icons/apple-touch-icon.png
rsvg-convert -w 96 -h 96 badge.svg -o ../public/icons/badge-96.png
```

# Manual de uso

GreenSense IoT muestra el estado del invernadero en tiempo real y avisa cuando algo se sale de lo adecuado. Funciona en el navegador de la computadora o del teléfono, donde también se puede instalar como aplicación.

## Roles

Lo que ves depende de tu rol. Quien administra el sistema te da de alta.

| Puedes | Operador | Supervisor | Técnico | Administrador |
|---|:-:|:-:|:-:|:-:|
| Ver el panel y el historial, y atender alertas | Sí | Sí | Sí | Sí |
| Recibir avisos del cultivo (rangos y hongos) | Sí | Sí | No | Sí |
| Recibir avisos de los dispositivos (sensor y desconexión) | No | No | Sí | Sí |
| Exportar reportes en CSV | No | Sí | No | Sí |
| Consultar la bitácora | No | Sí | No | Sí |
| Registrar y mantener nodos | No | No | Sí | Sí |
| Configurar cultivos, umbrales e invernaderos | No | No | No | Sí |
| Administrar usuarios | No | No | No | Sí |

## Entrar

Escribe tu correo y tu contraseña. La sesión dura 12 horas. Para cambiar tu contraseña, presiona tu nombre en la barra superior (**Mi cuenta**). **Salir** cierra la sesión y apaga las notificaciones de ese navegador.

## Panel

Muestra una tarjeta por nodo, con su última lectura. Arriba a la derecha, **En vivo** indica que los datos se actualizan solos.

| Color de la variable | Significado |
|---|---|
| Verde | Normal |
| Amarillo | Advertencia: cerca de un límite, o fuera de rango desde hace poco |
| Rojo | Crítica: fuera de rango durante el tiempo que marca el cultivo |

Debajo de cada variable está la gráfica de las **últimas 6 horas**, con su mínimo y su máximo. Al pasar el puntero o el dedo muestra el valor y la hora de ese punto. Si la línea se corta, faltaron lecturas.

En la tarjeta también aparecen las alertas de todo el nodo, como la desconexión o el riesgo de hongos.

## Alertas

El número rojo en la barra cuenta las críticas activas.

| Tipo | Cuándo aparece | Qué hacer |
|---|---|---|
| Rango del cultivo | Temperatura, humedad del aire o del sustrato cerca o fuera del rango | La alerta trae la recomendación, como ventilar o regar |
| Riesgo de hongos | Humedad y temperatura altas a la vez durante 1 hora | Ventilar y revisar hojas y tallos |
| Falla de sensor | Un sensor no entrega datos o da un valor imposible | Revisar su conexión |
| Nodo desconectado | El nodo lleva más de 5 minutos sin mandar lecturas | Revisar la alimentación y el WiFi |

- **Se cierran solas:** una alerta se resuelve cuando el valor vuelve a lo normal, con un pequeño margen para que no se abra y se cierre por variaciones mínimas.
- **Marcar como atendida:** registra quién la vio y a qué hora, pero no la resuelve.
- **Activas / Todas:** cambia entre las que siguen abiertas y todo el historial.
- **Filtros:** busca por severidad, variable y fechas. **Quitar filtros** regresa a la lista normal.

## Notificaciones

Presiona **Activar notificaciones** en la barra y acepta el permiso. Llegan cuando una alerta se vuelve crítica, aunque la app esté cerrada; al tocarlas se abren las alertas. El aviso depende de tu rol (ver la tabla). Necesitan que la app esté publicada con HTTPS.

Para **instalar la app** en el teléfono:
- **Android:** en el menú de Chrome, **Instalar aplicación**.
- **iPhone:** en Safari, **Compartir > Agregar a inicio**. En iPhone las notificaciones solo funcionan con la app instalada.

## Historial

1. Elige el **nodo** y, si quieres, una sola **variable**.
2. Elige el periodo: **Día**, **Semana**, **Mes** o **Rango**, donde eliges las fechas de inicio y de fin.
3. Muévete con las flechas o con la fecha.

Arriba está el resumen: promedio, mínimo, máximo y lecturas recibidas contra las esperadas. La franja gris de cada gráfica es el rango adecuado del cultivo. El día muestra cada lectura; los periodos largos muestran el promedio con una banda del mínimo al máximo. **Ver tabla** muestra los mismos datos como tabla.

**Lecturas CSV** y **Alertas CSV** descargan el periodo mostrado, con todas las variables, y se abren en Excel. Solo aparecen si tu rol puede exportar.

## Configuración

- **Cultivos y umbrales (administrador):** rango de cada variable, margen de la advertencia, tiempo para que sea crítica y condiciones de riesgo de hongos.
- **Invernaderos (administrador):** nombre y cultivo de cada uno.
- **Nodos (técnico y administrador):** alta, nombre, sensores y baja. Un nodo dado de baja conserva su historial, pero deja de generar alertas. Un nodo nuevo también necesita su usuario MQTT: ver el [manual de instalación](manual-instalacion.md).
- **Usuarios (administrador):** alta, rol, desactivar y restablecer contraseña. Los usuarios no se borran, para conservar su historial, y siempre debe quedar un administrador activo.

## Bitácora

Registra quién hizo qué y cuándo: altas, bajas, cambios con su valor anterior y nuevo, exportaciones e inicios de sesión. Las acciones hechas desde la línea de comandos aparecen como "Sistema".

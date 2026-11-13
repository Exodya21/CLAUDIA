# ADR-0009 · Portal propio del cliente y conversaciones por expediente

**Estado:** aceptada (Dirección, 06/11/2026: «tendremos un portal propio, no queremos depender de WhatsApp», T-31).

## Contexto
Con WhatsApp el historial vive en el móvil de cada trabajador, los números se bloquean y se pierde lo hablado al
cambiar de puesto. El documento «Portal de Comunicaciones Cliente–Despacho» se revisó frente al sistema el 06/11/2026
y la mitad de sus piezas ya existían (contacto maestro, expedientes, permisos, almacén cifrado, auditoría, tareas).

## Decisión
1. Las conversaciones son un **módulo del propio sistema** (no un chat externo ni un SDK con datos en terceros):
   `comm_thread` por expediente (y uno general por contacto), `comm_message` con visibilidad cliente/interna y
   nivel normal/importante/urgente, versiones de edición, adjuntos al almacén cifrado, marcas de lectura y
   confirmaciones de urgentes. Migración `0007`.
2. **Nada se borra**: ocultar al cliente con motivo; ediciones solo 15 minutos y con la versión anterior guardada;
   triggers que impiden DELETE y modificar historiales.
3. El **cliente** entra con código de un solo uso a su correo; su sesión es independiente de la del equipo.
4. Los **correos** salen por una cola con clave de idempotencia y adaptador (SMTP configurable); nunca llevan el
   contenido, solo «tiene un mensaje/aviso en su portal» (secreto profesional).
5. **Urgentes** solo con plantilla y fecha tomada de una tarea del expediente (plazo legal únicamente si lo validó
   un letrado), con confirmación obligatoria; sin confirmar en 24 h → tarea de llamada (una vez).
6. Los adjuntos del cliente pasan al expediente de extranjería con la **misma lectura** que una subida directa.
7. Exportación PDF con **huella SHA-256** del contenido (no es un sellado de tiempo cualificado).

## Consecuencias
- Sin cuotas por usuario ni datos de conversaciones en terceros (salvo el proveedor de correo, T-33).
- Pendiente de fase 2: SMS (T-35), notas de voz con transcripción, centralita (opciones A/B/C del documento),
  importación de chats de WhatsApp (en producción, con datos reales solo en infraestructura aprobada).
- Los requisitos de WhatsApp de la matriz se conservan, relacionados con este ADR, hasta el acta T-36.

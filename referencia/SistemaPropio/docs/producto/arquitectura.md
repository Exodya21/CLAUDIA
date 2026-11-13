# Arquitectura funcional y modelo de datos

Versión de trabajo 02/11/2026 · Estado: **propuesta para validación de Dirección** (no aprobada).

## 1. Principio rector

Un **monolito modular**: una sola API, una sola base de datos PostgreSQL y un solo modelo de identidad, dividido
en módulos con fronteras explícitas (paquetes y tablas propias, comunicación por servicios internos y eventos de
dominio). Los 18 módulos de la matriz (M00–M17) son módulos de este monolito, no aplicaciones separadas. Se podrá
extraer un módulo a un servicio aparte solo cuando un dato medido lo justifique (carga de OCR, por ejemplo).

Por qué no microservicios ahora: 47 personas usuarias, un equipo técnico pequeño y una regla dominante —los
permisos se deciden con datos de varios módulos a la vez (entidad, sede, rama, asignación)— que en un sistema
distribuido obligaría a replicar la autorización en cada servicio. Ver ADR-0001.

## 2. Mapa de módulos y dependencias

```mermaid
flowchart LR
    subgraph NUCLEO["M00 Núcleo (F0)"]
        IAM[Identidad, entidades, sedes, roles, autorizaciones]
        AUD[(Auditoría encadenada)]
    end
    M01[M01 Clientes y contactos]
    M02[M02 Captación / CRM]
    M03[M03 Citas y cobro]
    M04[M04 Fichas inteligentes]
    M05[M05 Expedientes]
    M06[M06 Cálculos laborales]
    M07[M07 Documentos y firma]
    M08[M08 Escritos laborales]
    M09[M09 Agenda, tareas y plazos]
    M10[M10 Notificaciones oficiales]
    M11[M11 Extranjería y nacionalidad]
    M12[M12 Comunicaciones]
    M13[M13 ATC / incidencias]
    M14[M14 Facturación]
    M15[M15 RRHH]
    M16[M16 Dirección y analítica]
    M17[M17 Integraciones, IA, colas]

    NUCLEO --> M01
    M01 --> M02 --> M03 --> M04 --> M05
    M05 --> M06 --> M08
    M05 --> M07
    M05 --> M09
    M05 --> M11
    M10 --> M09
    M05 --> M12
    M01 --> M13
    M13 -->|propuesta de devolución| M14
    M05 -->|resultado validado| M14
    M15 -.aislado de clientes.- NUCLEO
    M16 -->|solo lectura| M02 & M03 & M05 & M14
    M17 --- M07 & M10 & M12 & M04
```

Reglas de dependencia:
- Todos los módulos dependen de M00 para identidad, autorización y auditoría; **ninguno implementa su propio control de acceso**.
- M01 es la única fuente de la persona. Lead, cita, ficha, expediente, documento y factura **referencian** `contact.id`; nunca copian sus datos.
- M15 (RRHH) comparte identidad de empleados pero sus datos viven en tablas sin relación con clientes (AT-26).
- M16 solo lee; los KPI se calculan sobre los mismos registros operativos (AT-27), no sobre hojas paralelas.
- Todo proveedor externo (pasarela, WhatsApp, firma, OCR, IA, portales) entra por M17 mediante un adaptador con cola, reintentos e idempotencia.

## 3. Flujo de punta a punta (FL-01 → FL-08)

```mermaid
sequenceDiagram
    autonumber
    actor C as Cliente
    participant R as Recepción/ATC
    participant CRM as M02 Lead
    participant CI as M03 Cita
    participant P as Pasarela (adaptador M17)
    participant F as M04 Ficha
    participant A as Asesor / Letrado
    participant E as M05 Expediente
    participant AG as M09 Agenda
    participant FA as M14 Contabilidad

    C->>R: Contacta (canal con origen)
    R->>CRM: Crea lead (origen obligatorio, UTM si existe)
    R->>CRM: Busca/crea contacto maestro (aviso de duplicado)
    CRM->>CI: Solicita cita (rama > sede/modalidad > asesor opcional > hueco)
    CI->>P: Checkout (reserva provisional con caducidad)
    P-->>CI: Callback de pago (idempotente)
    CI->>CI: Cita confirmada (solo tras cobro)
    A->>F: Ficha según ruta (3 rutas laborales / trámite extranjería)
    A->>A: Propuesta de viabilidad (asesor)
    A->>A: Aprobación letrada (nunca ATC, nunca IA)
    A->>E: Encargo/firma → apertura de expediente (código consecutivo)
    E->>AG: Tareas y plazos (fecha legal validada ≠ objetivo interno)
    E->>FA: Resultado validado → propuesta económica
    FA->>FA: Contabilidad valida liquidación (D-05)
```

## 4. Modelo de datos

### 4.1 Implementado en F0.1 (migración `0001`)

```mermaid
erDiagram
    organization ||--o{ branch : tiene
    organization ||--o{ department : tiene
    organization ||--o{ membership : "pertenencia"
    user_account ||--o{ membership : tiene
    role ||--o{ membership : asigna
    role ||--o{ role_permission : concede
    user_account ||--o{ access_grant : "autorización puntual"
    organization ||--o{ contact : "titular del dato"
    contact ||--o{ identifier : documenta
    contact ||--o{ contact_point : "teléfonos y correos"
    contact ||--o{ address : domicilios
    contact ||--o{ consent : consentimientos
    contact ||--o{ duplicate_review : "posible duplicado"
    contact ||--o{ case_file : "N expedientes"
    department ||--o{ case_file : rama
    branch ||--o{ case_file : sede
    case_file ||--o{ case_assignment : responsables
    user_account ||--o{ case_assignment : asignado
    organization ||--o{ case_code_counter : numeración

    organization {
        uuid id PK
        text name
        char2 country
        char3 currency
        text status
    }
    branch {
        uuid id PK
        uuid organization_id FK
        text name
        text city
        text timezone
        text kind
    }
    department {
        uuid id PK
        uuid organization_id FK
        text code
        bool is_legal
    }
    user_account {
        uuid id PK
        text username UK
        text external_subject UK
        text status
        bool is_demo
    }
    role {
        uuid id PK
        text code UK
    }
    role_permission {
        uuid role_id PK
        text permission PK
    }
    membership {
        uuid id PK
        uuid user_id FK
        uuid organization_id FK
        uuid branch_id FK "nullable = todas"
        uuid department_id FK
        uuid role_id FK
        timestamptz valid_to
    }
    access_grant {
        uuid id PK
        uuid user_id FK
        text resource_type
        uuid resource_id
        text permission
        text reason
        timestamptz expires_at
        timestamptz revoked_at
    }
    contact {
        uuid id PK
        uuid organization_id FK
        text given_name
        text family_names
        text search_name
        bool possible_duplicate
        int version
        uuid created_by FK
    }
    identifier {
        uuid id PK
        uuid contact_id FK
        text kind
        text number_normalized
        char2 country
    }
    contact_point {
        uuid id PK
        uuid contact_id FK
        text kind "phone/email"
        text value_normalized "NO unico"
    }
    address {
        uuid id PK
        uuid contact_id FK
        text kind "postal/empadronamiento"
        text municipality
    }
    consent {
        uuid id PK
        uuid contact_id FK
        text purpose
        bool granted
        text source
    }
    duplicate_review {
        uuid id PK
        uuid contact_id FK
        uuid candidate_contact_id FK
        text status
    }
    case_file {
        uuid id PK
        uuid organization_id FK
        uuid department_id FK
        uuid branch_id FK
        uuid contact_id FK
        text code UK
        text materia
        text status
        text confidential_summary
    }
    case_assignment {
        uuid id PK
        uuid case_id FK
        uuid user_id FK
        text role_in_case
        timestamptz end_at
    }
    case_code_counter {
        uuid organization_id PK
        text prefix PK
        int year PK
        int last_value
    }
    audit_event {
        bigint id PK
        timestamptz occurred_at
        uuid actor_user_id
        text action
        text resource_type
        text outcome
        jsonb before
        jsonb after
        char64 prev_hash
        char64 hash UK
    }
```

Garantías en la propia base de datos (defensa en profundidad, no solo en la API):
- `audit_event`: triggers que rechazan UPDATE, DELETE y TRUNCATE; cadena SHA-256 verificable (`GET /audit-events/verify`).
- `case_file` y `contact`: trigger que impide el borrado físico (solo archivo lógico).
- `case_file`: trigger que impide mezclar contacto, sede o departamento de otra entidad.
- CHECK en materias, tipos de documento y tipos de contacto.
- Todas las fechas en `timestamptz` y sesiones de BD en UTC.

### 4.2 Modelo objetivo (se añade por incrementos, sin rehacer lo anterior)

```mermaid
erDiagram
    contact ||--o{ lead : "origen comercial"
    lead ||--o{ appointment : "solicita"
    appointment ||--o| payment_reference : "cobro previo"
    contact ||--o{ form_response : "ficha"
    form_template ||--o{ form_response : "versión usada"
    form_response ||--o{ employment_period : "periodos con/sin papeles"
    employer ||--o{ worksite : "centros de trabajo"
    employment_period }o--|| employer : con
    form_response ||--o{ extracted_field : "dato con origen (OCR)"
    document ||--o{ extracted_field : fuente
    case_file ||--o| form_response : "nace de"
    case_file ||--o{ case_relation : "relacionado con"
    case_file ||--o{ case_phase_event : "historial de fases"
    case_file ||--o{ task : tareas
    task ||--o{ task_event : "aplazamientos con motivo"
    legal_rule_version ||--o{ deadline : "regla aplicada"
    case_file ||--o{ deadline : "fecha legal validada + objetivo interno"
    case_file ||--o{ document : documentos
    document ||--o{ document_version : versiones
    document ||--o{ share_link : "enlace caducable"
    case_file ||--o{ signature_bundle : firma
    contact ||--o{ communication_event : interacciones
    case_file ||--o{ notification_event : "notificación oficial"
    contact ||--o{ ticket : "ATC"
    ticket ||--o| refund_request : "propuesta"
    refund_request ||--o| accounting_approval : "valida Contabilidad"
    case_file ||--o{ fee_settlement : "liquidación"
    organization ||--o{ invoice : "emisora"
    integration_event }o--|| organization : outbox
```

Convenciones que todo módulo nuevo debe respetar:
1. PK `uuid` técnica irreversible + código visible configurable cuando el negocio lo necesite.
2. `organization_id` en toda tabla con datos de negocio; nunca se consulta sin filtrarlo por la política de M00.
3. Datos derivados de documentos o IA llevan **origen** (documento, página/segmento, confianza, extractor, validado_por, validado_en). Un dato sin validar no se usa en cálculos ni escritos.
4. Reglas legales y fiscales viven en `legal_rule_version` (fuente, vigencia, territorio, aprobador). El código ejecuta la versión aprobada; nunca contiene plazos fijos.
5. Cambios relevantes: evento en `audit_event` en la misma transacción.
6. Integraciones: patrón *outbox* (`integration_event` con `idempotency_key`) y un worker; los callbacks externos se deduplican por clave.

## 5. Capas técnicas

| Capa | Tecnología | Estado F0.1 |
|---|---|---|
| Web | Next.js 15 (App Router) + TypeScript, proxy same-origin a la API | Implementada |
| API | FastAPI + Pydantic v2, `/api/v1`, OpenAPI en `/api/v1/docs` | Implementada |
| Datos | PostgreSQL 16, SQLAlchemy 2, Alembic (migraciones reversibles) | Implementada |
| Identidad | OIDC + MFA (proveedor por decidir, T-01); modo DEMO solo en desarrollo | DEMO implementado; OIDC = "No disponible aún" |
| Documentos | Almacenamiento S3 compatible cifrado, URLs temporales, antivirus | F2 |
| Asíncrono | Cola (Redis o tabla outbox + worker) con reintentos e idempotencia | F1.3 (pagos) |
| Observabilidad | Logs estructurados con `request_id`, métricas, alertas | Parcial (request_id) |

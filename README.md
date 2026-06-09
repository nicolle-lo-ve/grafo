#  GUÍA DE IMPLEMENTACIÓN DEL SISTEMA DE DETECCIÓN DE FRAUDES  
## Basada en el paper: *"Detección de Fraudes en la Contratación Pública Portuguesa mediante Análisis de Redes"*

---

##  Contexto y justificación (según el paper)

El paper propone un sistema de tres capas para detectar fraudes en contratación pública:

1. **Base de datos orientada a grafos**: almacena entidades (nodos) y contratos (relaciones). Permite descubrir patrones difíciles de ver con tablas tradicionales.
2. **Motor de reglas + análisis de redes**: añade etiquetas semánticas (fraude, sospecha) y calcula métricas como centralidad o PageRank.
3. **Dashboard visual y georreferenciado**: los auditores exploran el grafo, hacen clic en nodos/aristas y ven información relevante en paneles laterales. También hay filtros, búsquedas e histogramas.

Tu proyecto debe seguir **exactamente esa arquitectura**. Lo que ya tienes (`build_data.py`) es un buen inicio para la limpieza y preparación de datos, pero falta la parte central: **el grafo** y **el dashboard interactivo con paneles laterales**.

---

##  Paso 1 – Limpieza y preparación de datos (orientada a grafo)

### ¿Qué necesitas?
- Datos de contratos públicos (pueden ser del portal BASE.gov o similar). El paper usa:
  - Entidad adjudicadora
  - Entidad contratada
  - Fecha, valor, objeto, lugar, competidores, distancia geográfica
- Datos complementarios: ubicación (coordenadas), código de actividad económica.

### ¿Qué debes hacer exactamente?
1. **Extraer** desde la fuente (ya sea con web scraping o desde archivos como los que procesa tu script).
2. **Limpiar**:
   - Eliminar registros sin monto o sin fecha (como ya haces).
   - Imputar valores faltantes (medianas por categoría, no ceros absolutos si son montos).
   - Calcular **distancia geográfica** entre adjudicadora y contratada (usando coordenadas).
3. **Crear columnas que luego serán propiedades del grafo**:
   - Riesgo básico: sobrecosto (>120%), sin competencia (1 licitante), plazo corto (≤2 días).
   - Otras: monto, porcentaje adjudicado, número de licitantes, duración, etc.

>  Tu `build_data.py` ya hace gran parte de esto. Solo faltaría **calcular distancias** (si no lo tienes) y **estructurar los datos como lista de nodos y aristas** (en lugar de una tabla plana).

### Salida esperada de este paso:
Un DataFrame (o varios) con:
- **Nodos**: Identificadores únicos para cada entidad adjudicadora y cada proveedor.
- **Aristas**: Cada contrato con propiedades: `origen` (adjudicadora), `destino` (proveedor), `monto`, `fecha`, `riesgo`, `distancia`, `num_licitantes`, etc.

---

## 🕸️ Paso 2 – Creación de la base de datos orientada a grafos

### ¿Por qué una base de grafos?
El paper argumenta que los fraudes sofisticados (anillos de fraude, colusiones) no se detectan con tablas relacionales. Un grafo permite ver **quién se conecta con quién**, nodos centrales, comunidades, etc.

### Herramienta sugerida por el paper: **Neo4j** (gratuita, con Cypher como lenguaje de consultas).

### Pasos concretos:

1. **Instalar Neo4j** (versión community) o usar una instancia en la nube (AuraDB free).
2. **Modelar**:
   - **Nodos**:
     - `Entidad` (con propiedades: nombre, tipo, coordenadas, CAE, etc.)
     - Se pueden diferenciar por etiquetas: `Adjudicadora`, `Proveedor` (opcional).
   - **Relaciones**:
     - `CONTRATO` (con propiedades: monto, fecha, distancia, num_licitantes, riesgo, etc.)
3. **Cargar los datos limpios**:
   - Usar el driver de Python (`neo4j` o `py2neo`) o el comando `LOAD CSV` de Cypher.
   - Crear índices (por ejemplo, en `nombre` de entidad) para búsquedas rápidas.

### Comprobación:
Ejecuta consultas como:
```cypher
MATCH (a:Adjudicadora)-[c:CONTRATO]->(p:Proveedor)
RETURN a.nombre, p.nombre, c.monto, c.riesgo LIMIT 10
```

---

##  Paso 3 – Desarrollo del dashboard con grafo interactivo y paneles laterales

### ¿Qué pide el paper explícitamente?
> *"Una interfaz de usuario orientada a grafos se utiliza para apoyar la toma de decisiones, permitiendo a los usuarios explorar y filtrar información de manera rápida y eficiente, de forma natural y georreferenciada."*

Además, el auditor puede **hacer clic** en un nodo o arista y ver información detallada. También hay **búsquedas, filtros por fecha, ubicación, valor**, e **histogramas** (por ejemplo, distribución de montos o número de licitantes).

### Tecnologías sugeridas (compatibles con el paper y tu script actual):
- **Frontend**: HTML/CSS/JS, **D3.js** o **vis-network** para el grafo, **Leaflet** para mapa si quieres georreferenciación.
- **Backend (opcional)**: Si el grafo es grande, necesitarás una API (Flask/FastAPI) que consulte Neo4j y devuelva subgrafos. Para prototipo pequeño, puedes exportar el grafo a JSON y cargarlo directamente (similar a tu `cp_data.js`).

### Estructura del dashboard (tres secciones):

```
+-------------------------------------------------+
|  Barra superior: Filtros (fecha, monto, riesgo) |
+-------------------+-----------------------------+
|                   |                             |
|   Panel izquierdo |     VISUALIZACIÓN DEL       |
|   - Lista de      |          GRAFO              |
|     nodos         |   (nodos = entidades,       |
|   - Estadísticas  |    aristas = contratos)     |
|     básicas       |                             |
|   - Histograma    |   Interactivo:              |
|     de montos     |   - zoom, pan               |
|                   |   - clic en nodo/arista     |
+-------------------+-----------------------------+
|                   |                             |
|   Panel derecho   |   (Área dinámica)            |
|   - Detalles del  |   Al hacer clic se muestra: |
|     elemento      |   - Propiedades              |
|     seleccionado  |   - Gráficas relacionadas    |
|   - Métricas de   |     (ej. evolución temporal)|
|     red asociadas |                             |
+-------------------+-----------------------------+
```

### Requisitos funcionales exactos (según paper):

1. **Grafo georreferenciado**: Los nodos se posicionan en un mapa (opcional, pero muy valorado). Si no, se usa un layout tipo fuerza.
2. **Selección de nodo o arista**:
   - Al hacer clic en un nodo (entidad), el panel lateral muestra:
     - Nombre, tipo, ubicación, CAE.
     - Monto total de contratos (como adjudicadora o proveedora).
     - Número de contratos.
     - Histograma de montos a lo largo del tiempo (si hay fecha).
     - Lista de sus vecinos directos (con montos).
   - Al hacer clic en una arista (contrato), muestra:
     - Fecha, monto, distancia, número de licitantes, porcentaje adjudicado.
     - Si tiene alguna alerta (sobrecosto, plazo corto, sin competencia).
     - Las dos entidades involucradas (con enlace para seleccionarlas).
3. **Paneles laterales adicionales** (según el paper):
   - **Filtros**: por rango de fechas, por rango de monto, por tipo de riesgo, por departamento o proveedor.
   - **Histogramas**: distribución de montos, de distancias, de número de licitantes, de riesgo.
   - **Métricas de red globales**: densidad, número de componentes, PageRank de los nodos más importantes.
4. **Interactividad**: Al filtrar, el grafo se actualiza dinámicamente (se ocultan nodos/aristas que no cumplen).

### ¿Cómo lo implementas paso a paso (siguiendo el paper)?

#### a) Exportar el grafo desde Neo4j a un formato web
- Escribe una consulta Cypher que devuelva todos los nodos y relaciones (con propiedades relevantes) para un período o filtro inicial.
- Convierte el resultado a JSON con estructura:
  ```json
  {
    "nodes": [ { "id": "1", "label": "Municipio X", "group": "adjudicadora", "lat": -12.043, "lon": -77.028 } ],
    "edges": [ { "from": "1", "to": "2", "value": 50000, "date": "2024-01-01", "riesgo": 1 } ]
  }
  ```

#### b) Construir el HTML/JS
- Usa **vis-network** (más fácil) o **D3.js** (más flexible). El paper no especifica, pero puedes elegir.
- Integra **Leaflet** si quieres el mapa de fondo.
- Crea los paneles laterales con `<div>` flotantes o fijos.

#### c) Conectar la selección con los paneles
- Escucha el evento `"click"` en un nodo o arista.
- Obtén los datos desde el objeto del grafo o mediante una nueva consulta a Neo4j (más escalable).
- Actualiza los paneles con HTML dinámico (puedes usar plantillas o innerHTML).

#### d) Añadir histogramas
- Usa **Chart.js** o **D3.js** para dibujar histogramas (por ejemplo, de montos de los contratos mostrados).
- Los histogramas deben actualizarse al aplicar filtros.

---

##  Estructura de carpetas sugerida para GitHub (siguiendo el paper)

```
fraude-contrataciones-grafo/
│
├── data/                          # Datos crudos y procesados
│   ├── raw/                       # Archivos descargados (CSV, JSON)
│   └── processed/                 # Parquet o CSV limpio (generado por build_data.py)
│
├── notebooks/                     # Exploración (si usas Jupyter)
│   └── 01_limpieza.ipynb
│
├── scripts/                       # Scripts Python
│   ├── build_data.py              # Tu script actual (mejorado)
│   ├── load_to_neo4j.py           # Carga del grafo a Neo4j
│   └── graph_metrics.py           # Cálculo de centralidad, PageRank, etc.
│
├── dashboard/                     # Aplicación web (frontend)
│   ├── index.html                 # Página principal con grafo y paneles
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   ├── graph.js               # Inicializa y maneja el grafo
│   │   ├── panels.js              # Lógica de actualización de paneles laterales
│   │   ├── filters.js             # Filtros e histogramas
│   │   └── api.js                 # Llamadas a Neo4j (si usas backend)
│   └── assets/                    # Imágenes, iconos
│
├── backend/                       # (Opcional) API para consultar Neo4j
│   ├── app.py                     # Flask/FastAPI
│   └── queries.py                 # Consultas Cypher reutilizables
│
├── docs/                          # Documentación
│   └── guia_implementacion.md     # Este mismo documento
│
├── README.md                      # Explicación del proyecto, cómo ejecutarlo
├── requirements.txt               # Dependencias Python
└── .gitignore
```

---

## 🧪 Resumen de pasos a seguir (checklist)

###  Fase 1 – Datos
- [ ] Obtener datos de contrataciones (pueden ser de Perú o Portugal, pero estructura similar).
- [ ] Ejecutar `build_data.py` adaptado para calcular distancias y generar tabla de nodos/aristas.
- [ ] Validar que no haya valores nulos críticos (id de entidad, monto, fecha).

###  Fase 2 – Grafo
- [ ] Instalar Neo4j y crear una base de datos.
- [ ] Escribir script `load_to_neo4j.py` que lea el CSV limpio y cree nodos y relaciones.
- [ ] Definir índices y restricciones (unicidad de nombre de entidad).
- [ ] Probar consultas Cypher básicas.

###  Fase 3 – Dashboard
- [ ] Crear `dashboard/index.html` con un div para el grafo y dos divs laterales.
- [ ] Usar vis-network para dibujar el grafo (cargar datos desde un JSON o desde Neo4j vía API).
- [ ] Implementar evento de clic: mostrar en panel derecho las propiedades del nodo/arista.
- [ ] Agregar filtros (fecha, monto, riesgo) usando sliders o checkboxes.
- [ ] Agregar histograma de montos (con Chart.js) que se actualice con los filtros.
- [ ] (Opcional) Georreferenciar: posicionar nodos con lat/lon sobre mapa Leaflet.

###  Fase 4 – Mejoras según paper
- [ ] Calcular y mostrar en un panel métricas de red (centralidad de grado, PageRank).
- [ ] Permitir reglas personalizadas (por ejemplo, resaltar contratos con distancia > media).
- [ ] Añadir etiquetas semánticas (colorear nodos según tipo de entidad o nivel de riesgo).

---

##  Notas finales importantes (basadas en el paper)

- **El sistema no es solo una tabla ni un gráfico de barras**: el corazón es el **grafo interactivo**.
- **El auditor debe poder investigar haciendo clic**, no escribiendo consultas complicadas.
- **Los paneles laterales son vitales** para mostrar el contexto sin saturar la visualización principal.
- **El paper enfatiza la georreferenciación**: si puedes mostrar la distancia entre adjudicadora y contratada en un mapa, mucho mejor.
- **La limpieza de datos ya la tienes avanzada**; ahora concéntrate en construir el grafo y el dashboard.


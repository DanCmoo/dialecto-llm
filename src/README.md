# DIALECTO-LLM: framework y banco de consultas

## Instalación local

Desde la raíz del proyecto:

```powershell
python -m pip install -e .
```

## Uso

Validar las invariantes del diseño (permite modelos aún pendientes):

```powershell
dialectollm validate-config
```

Verificar que el estudio esté completo para conectar un ejecutor de consultas:

```powershell
dialectollm validate-config --ready
```

Validar una matriz completa de calificaciones:

```powershell
dialectollm validate-ratings ruta/a/calificaciones.csv
```

Validar el banco de 60 ítems y la plantilla de revisión de hablantes (línea base v1):

```powershell
dialectollm validate-item-bank
dialectollm validate-language-review src/data/validacion_hablantes_template.csv
```

Para revisar un borrador incompleto:

```powershell
dialectollm validate-ratings ruta/a/calificaciones.csv --allow-incomplete
```

La matriz usa una fila por evaluador, respuesta y dimensión. Columnas obligatorias: `response_id,item_id,dialect,model_alias,replicate,dimension,rater_id,score`. Los identificadores de ítem previstos son `I001` a `I060`; dialectos `co`, `mx`, `rio`, `std`; dimensiones `precision`, `comprehension`, `relevance`; puntuación entera 1--5. La validación completa requiere las 1.440 combinaciones de respuesta, las tres dimensiones y al menos dos evaluadores por celda respuesta-dimensión.

El banco v2 de trabajo está en `data/item_bank_v2.json`, con cuatro formulaciones dialectales por cada uno de los 60 ítems. La línea base v1 permanece en `data/item_bank_v1.json` y `data/item_bank_v1.csv`. La plantilla `data/validacion_hablantes_template.csv` tiene dos espacios por cada una de las 240 variantes; consulte el JSON v2 por ID para revisar el texto de cada estímulo. Cada formulación conserva estado de borrador hasta que dos revisores nativos o expertos registren naturalidad y equivalencia semántica (1--5) y la aprueben.

## Límites de esta iteración

Esta entrega cubre el banco, la configuración y los contratos de datos. No incluye llamadas a APIs, aleatorización de lotes, calificación automática ni análisis estadístico. Los modelos y el plan de análisis están propuestos en los documentos IEEE, pero `collection_ready` permanece en `false` hasta completar la revisión lingüística, aprobar el protocolo y cerrar el piloto y el presupuesto con uso real.

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

## Plan reproducible del piloto por API

La configuración propone `gpt-6-luna` y `gpt-6.1-terra`, ambos con `medium`, por la API de Responses. El primer plan conserva los seis ítems piloto. Una unidad completa contiene cuatro dialectos por tres repeticiones por modelo: 12 llamadas por modelo y 24 llamadas comparadas por ítem.

En la tabla de API Platform, al 11 de noviembre de 2026, Luna muestra 10 RPM y 60.000 TPM; Terra muestra 3 RPM y 10.000 TPM. La tabla no muestra RPD, pero durante el lote 2 la API devolvió HTTP 429 para ambos modelos con `requests per day (RPD): Limit 50, Used 50` y recomendó esperar 28 min 48 s. Por tanto, el límite efectivo apareció en el error de la API, no en la tabla visible. El límite local inicial de 50 intentos fue una suposición errónea; se elevó a 100 para no bloquear antes de la API, manteniendo pacing RPM y sin reintentos automáticos. Revisa **API Platform > Limits** antes de cada lote; ante un 429, registra el error y pausa.

Crear el manifiesto y el calendario sin hacer llamadas ni generar costo:

```powershell
dialectollm plan-pilot `
  --run-id piloto-pareado-2026-11-11 `
  --run-dir runs/piloto-pareado-2026-11-11
```

El comando congela copias del banco y la configuración, guarda sus hashes SHA-256, la semilla, los parámetros, el orden de las llamadas y la cantidad por lote. Los resultados, prompts y manifiestos quedan en `runs/`, excluida de Git.

Para ejecutar el primer lote, crea una clave API de proyecto en API Platform y guárdala localmente en `.env`. Copia `.env.example` a `.env` en la raíz del proyecto y asigna el valor a `OPENAI_API_KEY`. El ejecutor lee ese archivo sin mostrar la clave; las variables ya definidas en el proceso tienen precedencia. **No incluyas `.env` en el repositorio ni compartas la clave por el chat.** Después de revisar el manifiesto y comprobar el saldo/límite:

```powershell
dialectollm run-pilot runs/piloto-pareado-2026-11-11 --batch day1 --execute
```

El comando requiere `--execute` explícito. Registra estado, hora UTC, duración, ID de respuesta, modelo devuelto, tokens, costo estimado y salida. Si hay un error se detiene y conserva el intento, sin reintento automático. Al repetir el comando, omite llamadas completadas y continúa las pendientes; una llamada fallida requiere revisar el registro y usar explícitamente `--retry-failed` antes de repetirla, pues pudo generar cargo. El ejecutor cuenta intentos locales en una ventana móvil de 24 horas y no inicia un ítem parcial si el cupo local no permite el bloque pareado. Tras el 429, espera el intervalo informado y reanuda `day2` con `--retry-failed --execute`; las claves de llamada ya completadas no se duplican. Si se ejecuta un solo modelo con `--model-alias`, algunos pares pueden quedar pendientes hasta ejecutar el modelo compañero. Evita otras llamadas al mismo proyecto/modelos durante el lote, porque el proceso no puede contar tráfico externo.

### Supervisión y pausa segura

En otra terminal, desde `src/`, consulta el avance sin mostrar los textos de las respuestas:

```powershell
python -m dialectollm run-status ..\runs\piloto-pareado-20261111 --watch --interval 5
```

Para pedir una pausa segura, crea el marcador desde una segunda terminal:

```powershell
New-Item ..\runs\piloto-pareado-20261111\STOP_AFTER_CURRENT -ItemType File -Force
```

El ejecutor termina la llamada en curso, la guarda y se detiene antes de comenzar otra. Para continuar, elimina el marcador y vuelve a ejecutar `run-pilot` con el mismo lote. Las llamadas con estado `completed` se omiten. Evita `Ctrl+C` mientras haya una solicitud activa: el proceso puede interrumpirse antes de registrar la respuesta, aunque la API ya la haya procesado. Cada registro escrito normalmente se fuerza a disco con `fsync`.

El costo por respuesta se calcula con el uso devuelto por la API; `output_tokens` incluye tokens de razonamiento. El resumen final debe basarse en el uso facturado observado, no en el presupuesto preliminar.

`collection_ready` permanece en `false`: hay que registrar las revisiones lingüísticas dobles y aprobar académicamente la rúbrica y el análisis antes de habilitar el análisis principal. La plantilla de revisión no se marca como aprobada por el hecho de que no se hayan solicitado cambios.

## Corrida completa y reutilización del piloto

El protocolo actualizado considera **1.440 respuestas en total**: 60 ítems × 4 variedades × 3 repeticiones × 2 modelos. Los seis ítems piloto forman parte de esos 60. Sus respuestas completadas se reutilizan únicamente si coinciden clave de llamada, hash del prompt, modelo y parámetros de generación; se conservan además el ID de respuesta original y la procedencia del piloto. Así se ejecutan como máximo 1.296 llamadas nuevas.

Crear el plan local completo, dividido en lotes de hasta 48 llamadas por modelo (cuatro ítems por lote), sin consumir API:

```powershell
python -m dialectollm plan-full `
  --run-id experimento-completo-2026-11-12 `
  --run-dir ..\runs\experimento-completo-2026-11-12
```

Integrar las 144 respuestas completas del piloto:

```powershell
python -m dialectollm import-pilot `
  ..\runs\experimento-completo-2026-11-12 `
  ..\runs\piloto-pareado-20261111
```

Luego ejecutar un lote cuando haya cupo API, conservando la cadencia RPM del manifiesto:

```powershell
python -m dialectollm run-pilot ..\runs\experimento-completo-2026-11-12 --batch day1 --max-new-requests-per-model 24 --execute
```

Cada lote se reanuda con el mismo comando; las claves `completed` se omiten. Antes de cada lote, revisar el contador de solicitudes del proyecto y considerar llamadas realizadas por otros procesos. Los límites de 48 por modelo dejan dos solicitudes de margen frente al RPD observado de 50. Consultar avance con `run-status`. El plan completo mantiene `analysis_eligible=false` mientras sigan pendientes las aprobaciones registradas en `study_config.json`; esto no impide preservar y recolectar respuestas, pero sí advierte que la habilitación para análisis requiere resolver esos hitos.

## Límites de esta iteración

No incluye calificación automática ni análisis estadístico. El manifiesto y el JSONL de respuestas permiten reconstruir y reanudar la ejecución piloto, pero no sustituyen la aprobación metodológica ni la validación lingüística.

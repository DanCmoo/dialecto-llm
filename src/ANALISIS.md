# Análisis incremental y calificación independiente

Con la recolección pausada, desde la raíz del proyecto:

```powershell
python -m compileall -q src/dialectollm
python src/dialectollm/analysis.py runs/experimento-completo-2026-11-12
```

No realiza llamadas de red. Lee las entradas congeladas y respuestas; no las modifica. Trabaje sobre una copia consistente o pause el ejecutor: no se admite una lectura concurrente fiable. Cada ejecución reconstruye tablas derivadas sin acumular duplicados; conserva los códigos privados y las filas ya calificadas y añade espacios nuevos. No cambie ni distribuya `clave_privada.json`, `clave_correspondencia_PRIVADA.csv`, las tablas privadas ni el calendario. Todo está en `runs/`, excluido por Git. Respalde la clave y calificaciones de forma segura: perder la clave impide incorporar el trabajo anterior. Los códigos son aleatorios y estables, pero el texto de la consulta revela inevitablemente pistas de variedad; el cegamiento de variedad es parcial. El evaluador tampoco debe consultar el banco, calendario, identidad del modelo ni respuestas del otro evaluador. El material incluye criterios de referencia del banco, no identificadores del ítem ni modelo; pueden contener pistas del contenido.

Entregue a cada persona solo su archivo `evaluador_N_material.csv` y su propio `evaluador_N_calificaciones.csv`. Son CSV UTF-8 con campos entrecomillados; ábralos en una aplicación que preserve celdas multilínea y ceros y guárdelos en UTF-8. No comparta los archivos de calificaciones hasta que ambas personas terminen. Cada una asigna el mismo identificador seudónimo estable y distinto en `rater_id` en cada fila que complete; nunca registre nombres personales. Hay una fila por código y dimensión. Registre una puntuación entera 1–5 o marque `no_evaluable` como `si` y explique el motivo, sin puntuación; `no` o vacío significa evaluable. Una fila totalmente vacía en los campos de decisión queda pendiente. Registre una justificación breve para cada decisión y evite discutir respuestas durante la calificación. Si modifica una calificación, conserve una copia fechada de la versión anterior fuera del archivo de trabajo; la adjudicación, si se requiere, se registra aparte y nunca reemplaza las calificaciones originales.

- Precisión: 1 errores centrales; 3 mayoritariamente correcto con omisión o error menor; 5 correcto y completo, sin afirmaciones no sustentadas relevantes.
- Comprensión (`comprehension`): 1 interpreta mal la intención; 3 atiende el propósito general pero omite una restricción; 5 atiende la intención y las restricciones explícitas.
- Relevancia (`relevance`): 1 ajeno o evasivo; 3 parcialmente pertinente o con desvíos; 5 aborda lo solicitado sin contenido irrelevante sustancial.
- Use 2 y 4 como niveles intermedios según juicio; estos puntos no tienen anclajes específicos aprobados. La rúbrica es propuesta y requiere aprobación y calibración con respuestas de práctica excluidas del análisis.

Guarde los dos archivos recibidos en su ubicación original y vuelva a ejecutar el comando. La validación verifica códigos, dimensiones, identidad, duplicados, rango y no evaluables, y produce `errores_calificaciones.csv`; si hay errores no publica datos validados. Las filas pendientes no son puntuaciones. Las tablas `calificaciones_pares_exploratorios.csv` y `calificaciones_pares_pendientes.csv` separan pares con dos evaluadores por respuesta y dimensión de los demás. No ejecutan inferencia ni equivalen al análisis primario. El script no calcula kappa ni comprueba independencia real: debe hacerlo el equipo, conservar versiones, calibrar y registrar acuerdos y aprobaciones. La presencia de dos seudónimos no demuestra independencia.

`pares_completos.csv` contiene diferencias de tokens de salida y caracteres, no calidad; A es Luna y B Terra. `pares_pendientes.csv` distingue pares con una respuesta de pares sin ninguna. `cobertura.csv`, `incidencias.csv`, `intentos_historicos.csv` y `resumen.json` permiten auditar la corrida. Los costos son estimaciones a las tarifas congeladas y excluyen posibles cobros de intentos fallidos; los tokens de razonamiento están incluidos en los tokens de salida.

El análisis confirmatorio no se ejecuta aquí. Requiere registrar la revisión lingüística doble, aprobación académica de rúbrica y plan, calibración/acuerdo y calificaciones suficientes; definir tratamiento de no evaluables y verificar el estado de elegibilidad sin modificar retroactivamente el manifiesto. El plan pendiente especifica promedio entre evaluadores y luego tres repeticiones por ítem, contrastes de cada dialecto frente a estándar por modelo y dimensión, Wilcoxon bilateral pareado, correlación biserial por rangos, bootstrap pareado por ítem de 10.000 remuestras con semilla 20261103 y Holm por los tres contrastes de cada familia modelo-dimensión. La comparación entre modelos de este flujo es exploratoria, no sustituye ese plan.

## Reproducir el informe del corte sin API

Los dos programas validan los registros antes de exportar y comparten el bloqueo `analisis/.analisis.lock`. Si una ejecución termina abruptamente, compruebe que no queda un proceso activo antes de retirar ese bloqueo. Las escrituras son atómicas por archivo, no por conjunto: consulte el estado de validación del JSON y no use tablas antiguas después de un error. Se comprueba que las fuentes no cambien durante la lectura; mantenga pausada la recolección y la edición de calificaciones durante la actualización. Los errores de calificación conservan las hojas humanas, incluidas sus columnas adicionales, y suspenden la publicación de puntuaciones validadas.

Pruebas locales con datos sintéticos, sin acceso a la API: desde `src/`, ejecute `python -m unittest discover -s tests -q`.

Desde la raíz, con el piloto y la corrida principal originales en `runs/`:

```powershell
$run = 'runs/experimento-completo-2026-11-12'
Push-Location src
python -m dialectollm run-status "../$run"
Pop-Location
python src/dialectollm/analysis.py $run
python src/dialectollm/indicadores_objetivos.py $run
```

El último comando genera `indicadores_objetivos.json`, `indicadores_pares.csv` y `marcadores_numericos.csv` en `analisis/`. Compara ítems completos y registra en el JSON los denominadores por contraste entre modelos y frente al control. Los CSV contienen las medidas por par y la detección de marcadores. Un 1 indica presencia textual y un 0 indica ausencia, no error. No incorpora esas etiquetas a la rúbrica humana. Compare las huellas SHA-256 de los dos resúmenes para confirmar que parten del mismo archivo de respuestas.

El [informe](../docs/informe_proyecto.md) corresponde al corte del 13 de noviembre de 2026 y contiene cifras revisadas. Para regenerar su presentación (no recalcula las cifras), use Python con ReportLab:

```powershell
python src/render_informe.py docs/informe_proyecto.md
```

El comando escribe el PDF de lectura y la fuente LaTeX IEEEtran desde el mismo texto. El PDF se compone con ReportLab; si dispone de una distribución TeX y de IEEEtran, puede compilar también la fuente `.tex`.

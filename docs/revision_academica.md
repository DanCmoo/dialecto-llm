# Revisión académica y técnica del corte

Fecha: 12 de noviembre de 2026. Documento revisado: `informe_proyecto.md`, con fuente IEEEtran y PDF de lectura. Dictamen: informe exploratorio reproducible; requiere revisión metodológica y evaluación humana antes de sostener resultados confirmatorios de desempeño.

## Criterios consultados

Se utilizaron como referencias de revisión, sin atribuir al proyecto una certificación editorial:

1. IEEE Author Center, [Structure Your Article](https://journals.ieeeauthorcenter.ieee.org/create-your-ieee-journal-article/create-the-text-of-your-article/structure-your-article/): coherencia entre pregunta, métodos, resultados y discusión; contribución y limitaciones explícitas.
2. ACL Rolling Review, [Responsible NLP Research](https://aclrollingreview.org/responsibleNLPresearch/): documentación de datos, evaluadores, limitaciones y uso de herramientas de asistencia.
3. NeurIPS, [Paper Checklist](https://neurips.cc/public/guides/PaperChecklist): correspondencia entre afirmaciones y evidencia, reproducibilidad y transparencia sobre incertidumbre y recursos.
4. SciPy, [Wilcoxon](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html): hipótesis sobre las diferencias pareadas y tratamiento explícito de ceros, empates y procedimiento de cálculo.

## Correcciones realizadas

Tres revisiones delegadas cubrieron estructura de tesis, metodología e integridad del código; sus observaciones se integraron y verificaron localmente. Estos agentes no calificaron respuestas como evaluadores humanos independientes.

- Se precisó la pregunta primaria: cada variedad frente al control dentro de modelo y dimensión. La comparación entre modelos es exploratoria.
- Se separaron protocolo suministrado, decisiones registradas y desviaciones. El alcance de referencia es seis semanas, dos modelos y 1.440 respuestas, incluyendo las 144 del piloto.
- Se explicitó la agregación por ítem, las tres repeticiones, los dos evaluadores, el alcance de Holm por familia y las decisiones estadísticas pendientes. Las réplicas no se cuentan como ítems independientes.
- Se distinguieron diferencias de consumo, coincidencias textuales y desempeño humano. La sensibilidad al retirar un ítem no se presenta como intervalo de confianza.
- Se registró la falta de equivalencia explícita de una restricción en I011, la anotación morfosintáctica pendiente y las variaciones pragmáticas introducidas durante la construcción. El banco congelado permanece intacto.
- Se incorporaron composición de la muestra, falta de justificación de potencia registrada, selección por disponibilidad, limitaciones del cegamiento, disponibilidad de datos y uso de asistencia de IA.
- El código rechaza registros inconsistentes antes de exportar materiales, preserva hojas humanas y columnas adicionales, valida identidades y puntuaciones parciales y protege escrituras mediante reemplazo atómico y bloqueo común.

## Evidencia de verificación

`run-status` y ambos programas offline se ejecutaron sobre el estado real: 288 respuestas únicas de 1.440, 144 por modelo, 12 ítems completos y 144 pares completos. Hay 576 condiciones sin respuestas y ninguna con un solo modelo. El intento fallido histórico del registro principal está resuelto. Los cuatro fallos históricos del piloto también constaban resueltos en su registro de origen.

La auditoría devuelve cero incidencias técnicas, cero errores de calificación y cero puntuaciones humanas. Las dos plantillas contienen 864 filas pendientes cada una. La huella SHA-256 de respuestas se conserva: `4e28d83b10cb1aed70607487fedfc119f8115414b287983a0b8147e0b0cdd6ca`.

Pasaron las 11 pruebas sintéticas de integridad, preservación de calificaciones, registros duplicados, tokens inválidos, bloqueo, instantáneas incompletas y repetibilidad. Se revisaron visualmente las seis páginas del PDF. El PDF se compone con ReportLab; la fuente IEEEtran se entrega, pero no se verificó su compilación con una distribución TeX.

## Pendientes para el equipo académico

Se requieren revisión lingüística independiente y decisión documentada sobre equivalencia y elegibilidad; aprobación de rúbrica, tratamiento de no evaluables y plan estadístico; calificación por dos personas independientes, calibración y acuerdo; y definición del procedimiento de consistencia. Cualquier decisión posterior a la inspección debe fecharse y declararse como tal. No debe describirse como prerregistro.

La recolección queda pausada. No se generaron respuestas nuevas ni puntuaciones humanas sintéticas. La ausencia de evidencia suficiente para una conclusión confirmatoria es un resultado del estado del proyecto, no un motivo para buscar selectivamente significación estadística. Los comandos de actualización se mantienen en `src/ANALISIS.md`; las tablas se recalculan y el manuscrito requiere sincronización explícita de cifras en cada nuevo corte.

# DIALECTO-LLM: estudio pareado y análisis exploratorio del español dialectal
Grupo 3 · Corte de datos: 13 de noviembre de 2026

Resumen. Se presenta un framework para comparar, dentro de cada modelo de lenguaje, el desempeño ante consultas en español colombiano, mexicano y rioplatense frente a un control estandarizado. El diseño prevé 60 ítems, dos modelos y tres repeticiones por condición. Se auditaron las 480 respuestas disponibles de 20 ítems, incluidas 144 del piloto. La revisión encontró correspondencia de claves y hashes y una cobertura sobrerrepresentada por tareas de cálculo. En el análisis exploratorio, Luna registró 22,00 tokens de salida adicionales por respuesta en rioplatense frente al control, concentrados en razonamiento. El marcador de la clave apareció en las 192 respuestas de los ocho ítems verificables. Estos resultados describen consumo y presencia textual en el corpus observado. La comparación de precisión, comprensión, relevancia y consistencia requiere completar la evaluación humana y revisar la equivalencia de las consultas, afectada por diferencias explícitas de restricciones en un ítem examinado.

Palabras clave. Variación dialectal, modelos de lenguaje, evaluación pareada, auditoría, reproducibilidad.

## Introducción y preguntas de investigación

Las consultas de usuarios hispanohablantes presentan variación regional en vocabulario y gramática. Evaluar cómo responde un modelo exige mantener el contenido de la tarea al comparar sus formulaciones. DIALECTO-LLM desarrolla esa comparación sobre respuestas abiertas y documenta el vínculo entre banco, ejecución y evaluación. Este corte aporta un framework reanudable, una auditoría de datos y un análisis descriptivo por ítem que permite examinar la viabilidad del diseño.

El objetivo general [1] es evaluar en seis semanas si la precisión, comprensión, consistencia y relevancia de dos modelos de lenguaje presentan diferencias estadísticamente significativas al responder consultas semánticamente equivalentes en español colombiano, mexicano y rioplatense frente al español estandarizado (neutro). El diseño empareja las consultas por ítem y compara cada variedad con el control dentro de cada modelo. El nivel de significación es 0,05 con corrección de Holm-Bonferroni.

Los objetivos [1] y la metodología [2] fijan el alcance de seis semanas y dos modelos. La propuesta inicial del estado del arte [3] contemplaba 12 semanas y entre dos y tres modelos. La recolección tuvo pausas por el límite diario de solicitudes (RPD) y se amplió hasta el corte actual. Los análisis exploratorios de este informe usan las respuestas y los parámetros registrados hasta el corte.

La pregunta principal es si cambia la puntuación de cada dimensión al sustituir la formulación estándar por una regional, manteniendo ítem y modelo. La pregunta exploratoria de este corte es cómo varían el consumo y la longitud de salida bajo esas mismas condiciones y qué cobertura tiene una comprobación numérica acotada. El tamaño de 60 ítems procede del diseño suministrado. Los archivos revisados carecen de un cálculo de potencia o de un efecto mínimo relevante. La detención respondió a disponibilidad de cuota y las métricas exploratorias se definieron después de recopilar las respuestas.

## Estado del arte

La revisión del Grupo 3 [3] sitúa la variación dialectal en el estudio del sesgo lingüístico. Blodgett et al. [4] proponen definir qué conducta del sistema se mide, a quién afecta y por qué. Muñoz-Basols et al. [5] estudian el sesgo lingüístico digital en los modelos de español. SESGO incorpora expresiones latinoamericanas para evaluar estereotipos sociales en contextos ambiguos [6]. En DIALECTO-LLM, la variable de interés es la formulación dialectal de la consulta y la respuesta se evalúa en las cuatro dimensiones del objetivo general.

Los estudios de español ofrecen antecedentes con distintas unidades de evaluación. España-Bonet y Barrón-Cedeño construyeron el corpus CEREAL para caracterizar la variación regional y clasificar textos por variedad [7]. Mayor-Rocher et al. evaluaron a nueve modelos en siete macroáreas con un test de opción múltiple. La variedad peninsular fue la mejor identificada y Colombia no constituyó una categoría independiente [8]. Kawasaki evaluó juicios sobre el uso regional de 934 ítems léxicos en 21 países y encontró diferencias entre modelos, países y formatos [9]. La Leaderboard reúne conjuntos de evaluación para variedades del español y otras lenguas de España y América Latina [10].

XNLIvar aporta un antecedente de curaduría manual de conjuntos paralelos para inferencia en español y euskera. Sus autores observaron una caída de desempeño ante la variación, especialmente en euskera [11]. VALUE construyó ejemplos paralelos mediante transformaciones léxicas y morfosintácticas y recurrió a hablantes del inglés vernáculo afroamericano para validar su aceptabilidad [12]. En conjunto, estos diseños sustentan la decisión de emparejar consultas y verificar que cada reformulación preserve su significado y resulte natural.

Para generación abierta, Oh et al. construyeron diálogos paralelos en nueve variedades del inglés y validaron las transformaciones con lingüistas [13]. El preprint de Yagubyan observó que dos jueces automáticos invirtieron sus preferencias en un 13,6 % de evaluaciones pareadas repetidas, en promedio, dentro de su estudio [14]. Estos antecedentes orientan la calibración y la medición del acuerdo entre los evaluadores del proyecto. La revisión del Grupo 3 identifica como aporte del diseño combinar respuestas abiertas, las tres variedades seleccionadas y comparaciones pareadas contra un control, por modelo y dimensión [3].

## Metodología y decisiones del proyecto

### Diseño de referencia

El diseño [1], [2] prevé 60 ítems con cuatro formulaciones por ítem, dos modelos y tres repeticiones por combinación. El banco limita la variación prevista a rasgos léxicos y morfosintácticos. Se exige verificar equivalencia semántica y naturalidad, documentar los rasgos, aleatorizar el envío y registrar las llamadas en una bitácora. La precisión, la comprensión y la relevancia se puntúan de 1 a 5. La consistencia se mide por estabilidad entre repeticiones. La evaluación se plantea a ciegas respecto de la variedad, con un kappa ponderado mínimo de 0,60 y una meta de 0,70 o superior [1].

El protocolo del repositorio [15] especifica dos evaluadores independientes, pesos cuadráticos para kappa, anclajes de rúbrica y agregación por ítem. El banco v2 [16] conserva los identificadores, claves de respuesta y metadatos léxicos del banco inicial. Sus anclajes urbanos son Bogotá, Ciudad de México y Buenos Aires. La versión estándar se define como español escrito panhispánico neutral. Los 60 ítems figuran como borradores con revisión de hablantes pendiente. Los metadatos heredados requieren completar la anotación morfosintáctica por variante.

La construcción registrada en REFACTOR.md también promueve asimetrías de longitud, cambios de registro y rasgos pragmáticos intensificados. Este procedimiento amplía la manipulación respecto del límite léxico y morfosintáctico de los objetivos. La revisión lingüística deberá comprobar qué información y restricciones conserva cada formulación antes de interpretar un contraste como diferencia atribuible a la variedad.

### Cambios y desviaciones

El protocolo inicial separaba el piloto de la muestra principal. El addendum [17] incorpora sus 144 respuestas al total de 1.440 cuando coinciden clave, consulta, modelo y parámetros. Los seis ítems piloto pertenecen al banco de 60. La propuesta de la semana 2 consideraba dos proveedores. La ejecución usa dos modelos de OpenAI. El límite RPD detuvo la recolección y el estudio conserva la marca analysis_eligible=false, con la revisión lingüística y la aprobación académica pendientes.

### Configuración efectiva

El manifiesto identifica gpt-6-luna (Luna) y gpt-6.1-terra (Terra), con esfuerzo nominal medium, un solo turno y máximo de 1.024 tokens de salida. La instrucción común solicita responder en español de forma precisa y concisa, respetar las restricciones explícitas, indicar supuestos cuando falte una solución única y evitar datos locales no solicitados. Su texto exacto se conserva en la configuración. Se omitieron temperatura y top_p, se desactivaron herramientas y se solicitó store=false. La semilla 20261103 determina el calendario, con 15 lotes previstos de cuatro ítems y orden pareado. Los nombres devueltos coinciden con los solicitados. Al ser alias móviles, permiten rastrear el servicio declarado pero restringen la identificación de la versión interna.

Las respuestas observadas se obtuvieron entre el 11 de noviembre de 2026 a las 16:34:21 UTC y el 13 de noviembre (último intento: 20:57:59 UTC). Los bloques piloto son I001, I011, I021, I031, I041 e I051. Los catorce bloques añadidos corresponden a I002–I010 e I012–I016. La disponibilidad de los bloques, y no un muestreo aleatorio de los 60 ítems para este análisis, determina el corpus del corte.

### Evaluación humana y análisis de desempeño previsto

Las dos hojas tienen 1.440 espacios cada una (480 respuestas por tres dimensiones) y cero puntuaciones reales. Cada evaluador recibirá códigos aleatorios estables, consulta, respuesta y clave de referencia. La asignación conserva las etiquetas de modelo fuera del material entregado. La consulta contiene señales de variedad, por lo que el cegamiento respecto del dialecto será parcial. Deben registrarse la competencia lingüística, la formación recibida y la identidad seudónima de los evaluadores. Su selección y la calibración siguen pendientes. Las respuestas no evaluables se acompañarán de un motivo, preservando las puntuaciones originales y cualquier adjudicación por separado.

Tabla 1. Anclajes propuestos para la rúbrica ordinal [15].

| Dimensión | 1 (baja) | 3 (media) | 5 (alta) |
| --- | --- | --- | --- |
| Precisión | Error central | Correcta en lo esencial | Correcta y completa |
| Comprensión | Intención mal interpretada | Propósito general con una omisión | Intención y restricciones atendidas |
| Relevancia | Ajena o evasiva | Pertinente en parte | Directa y pertinente |

El plan [15] define la siguiente agregación. Para un ítem i, modelo m, variedad v y dimensión d, Q(i,m,v,d) será el promedio de las tres repeticiones, después de promediar evaluadores en cada respuesta. La diferencia pareada será Delta(i,m,v,d) = Q(i,m,v,d) − Q(i,m,std,d). La media de Delta resume la diferencia en puntos de rúbrica por ítem. Cada contraste tendrá como tamaño muestral el número de ítems con ambas condiciones evaluadas. Las repeticiones y los evaluadores aportan mediciones dentro del ítem.

El protocolo propone Wilcoxon bilateral y correlación biserial por rangos, junto a mediana de diferencias y un intervalo del 95 % para la diferencia media mediante bootstrap pareado de ítems (10.000 remuestras, semilla 20261103). El contraste de Wilcoxon se refiere a la distribución de las diferencias respecto de cero. Su interpretación como desplazamiento requiere justificar la simetría y resolver el tratamiento de ceros, empates y cálculo del valor p [18]. Estas precisiones se documentan durante esta revisión y siguen pendientes de aprobación metodológica. La comparación de desempeño aún carece de puntuaciones.

La configuración agrupa los tres contrastes variedad–control en cada familia de modelo y dimensión. Para precisión, comprensión y relevancia hay seis familias y 18 contrastes. Holm-Bonferroni controla el error al nivel 0,05 dentro de cada familia. El alcance de una afirmación conjunta del estudio debe corresponder a esa elección o a una enmienda explícita del plan. Para consistencia se proponen el rango y el acuerdo exacto entre las tres puntuaciones de repetición. Sus pruebas y familia de multiplicidad requieren especificación. El mínimo de kappa ponderado de 0,60 y la meta de 0,70 se comprobarán por dimensión antes de cerrar la evaluación.

La revisión semántica, los criterios para no evaluables, la política de exclusiones y la aprobación del plan constituyen pendientes documentados. Cualquier modificación motivada por esta inspección deberá conservar la fecha y su justificación. La aprobación posterior no puede acreditarse como preregistro anterior a las respuestas. Si se califican las 480 salidas actuales, el análisis describirá el subconjunto de 20 ítems y su composición.

### Análisis exploratorio ejecutado

Se incluyeron únicamente ítems con las cuatro variedades, tres repeticiones y ambos modelos completados. Se comprobaron claves, IDs, prompts, modelos, estados y tokens antes de producir tablas. El análisis descriptivo promedia las diferencias entre modelos dentro de cada ítem y luego entre ítems. Los contrastes variedad–control se calculan por repetición y se promedian por ítem. La sensibilidad a retirar un ítem vuelve a calcular la media sobre los diecinueve restantes, usando todos los ítems posibles. Estas reglas caracterizan el conjunto observado y se registraron después de la recolección.

Los costos se estiman a partir de entrada y salida a las tarifas conservadas en el manifiesto. Por millón de tokens, Luna usa USD 0,10 de entrada y 0,50 de salida, y Terra USD 1,00 y 5,00, respectivamente. La suma de salida incluye los tokens declarados de razonamiento. La comprobación numérica usa expresiones regulares versionadas sobre la clave de ocho ítems. Su denominador y los casos reconocidos se conservan en una tabla derivada.

## Software y trazabilidad

El framework de Python no requiere interfaz gráfica. El banco versionado y la configuración alimentan el planificador; este genera calendario y manifiesto. El ejecutor registra estado, hora, modelo solicitado y devuelto, hash de la consulta, respuesta, latencia, tokens, costo estimado y procedencia. El estado distingue éxitos únicos de intentos fallidos, y la reanudación conserva los éxitos. La auditoría comprueba la correspondencia entre calendario y log, exporta hojas ciegas y reconstruye tablas derivadas sin agregar duplicados. Se incorporó un script local para indicadores técnicos y marcadores numéricos.

La revisión de este corte comprobó que coinciden los hashes del banco, configuración y calendario congelados y los hashes de prompts; verificó 480 IDs y claves completadas únicas, ninguna salida vacía y correspondencia de ID y texto para las 144 respuestas importadas. El registro principal contiene 481 intentos, con un HTTP 429 de RPD resuelto después por la misma clave. El piloto conserva cuatro fallos 429 también resueltos en su propio registro; estos intentos no se incorporaron como respuestas. Se excluyeron las copias de prueba y sus puntuaciones sintéticas.

## Cobertura observada

Cada ítem completo aporta 24 respuestas: cuatro variedades por tres repeticiones por dos modelos. Un par entre modelos corresponde a un mismo ítem, variedad y repetición. Hay 240 pares completos, ninguno con un solo modelo y 480 sin respuesta. Las 960 respuestas faltantes corresponden a 40 ítems enteros. Esto permite comparar condiciones dentro de los 20 ítems observados, pero no atribuir la misma cobertura a las seis categorías de tareas.

Tabla 2. Cobertura del diseño y del corpus disponible.

| Unidad | Previsto | Observado |
| --- | --- | --- |
| Ítems | 60 | 20 |
| Respuestas | 1.440 | 480 (33,33 %) |
| Pares entre modelos | 720 | 240 |
| Respuestas por modelo | 720 | 240 |
| Respuestas por variedad | 360 | 120 |
| Respuestas por modelo y variedad | 180 | 60 |

El piloto aporta seis ítems, uno por categoría. Los catorce adicionales incluyen nueve de cálculo y cinco de procedimiento. El corpus contiene diez ítems de cálculo, seis de procedimiento y uno de cada categoría restante: explicación, recomendación, resumen y razonamiento. Procedencia, categoría y ventana de ejecución están confundidas. El equilibrio por variedad y modelo no corrige esta composición.

## Resultados exploratorios

### Consumo, longitud y costo

Se calcula Terra menos Luna para cada par y se promedian las 12 condiciones por ítem antes del resumen global. Los 20 ítems son los bloques de comparación; sus 240 pares no se cuentan como observaciones independientes para inferencia. Se informa sensibilidad al retirar un ítem, sin valores p. El costo aplica las tarifas congeladas a entrada y salida; no es una factura ni incorpora cargos no observados de intentos fallidos.

Tabla 3. Uso agregado de 240 respuestas por modelo.

| Indicador | Luna | Terra |
| --- | --- | --- |
| Tokens de entrada | 20433 | 20433 |
| Tokens de salida | 27917 | 24843 |
| De ellos, razonamiento | 13941 | 10869 |
| Salida menos razonamiento | 13976 | 13974 |
| Costo estimado (USD) | 0.0160018 | 0.1446480 |

El costo estimado total fue USD 0.1606498. Terra consumió 12,81 tokens de salida menos por par, con 12,80 tokens menos de razonamiento. La diferencia de salida menos razonamiento fue -0,008 tokens y la de longitud visible -0,125 caracteres por par. Su costo agregado fue 9,04 veces el de Luna.

La diferencia de salida fue negativa en 17 de 20 ítems. Al retirar un ítem, la media Terra menos Luna varió entre -16,81 y -10,39 tokens. Estos rangos describen sensibilidad; no son intervalos de confianza. Los contrastes de uso no miden calidad ni aíslan una causa dialectal. La latencia combina servicio, red y momento de la solicitud.

### Variedades frente al control

Se calculó variedad menos estándar por modelo, emparejando ítem y número de repetición y promediando dentro de cada ítem. Cada contraste usa los mismos 20 ítems y 60 pares. Emparejar por repetición alinea el diseño, pero no sincroniza la aleatoriedad de generación. La tabla presenta los seis contrastes de consumo.

Tabla 4. Diferencias medias de tokens de salida respecto del estándar.

| Variedad | Luna | Terra |
| --- | --- | --- |
| Colombiano | -0,48 | -3,22 |
| Mexicano | 14,37 | 1,20 |
| Rioplatense | 22,00 | 4,73 |

Para Luna, rioplatense menos estándar dio +22,00 tokens de salida, con incremento en 14 de 20 ítems. Al retirar un ítem, la media varió entre +12,74 y +27,23. La diferencia fue +27,60 en razonamiento y -5,60 en salida menos razonamiento, junto a -30,97 caracteres. En Terra, el contraste de salida fue +4,73 y su sensibilidad varió entre +0,86 y +8,67. Estos rangos no son intervalos de confianza ni demuestran diferencias de desempeño.

### Presencia de un marcador de la clave

Como comprobación acotada de contenido, se eligieron los ocho ítems observados cuya clave congelada especifica una cantidad con unidad o una hora única: I001–I007 e I051. Se buscó un marcador literal normalizado por cantidad y unidad u hora, comprobando primero que el patrón coincide con la clave. La regla usa normalización Unicode y de mayúsculas y minúsculas, retira marcas de formato y admite las abreviaturas expresamente codificadas. Una coincidencia cuenta como presencia y una ausencia exigiría revisión; no se transforma en una puntuación.

El marcador estuvo presente en 192 de 192 respuestas: 96 de 96 por modelo, en 96 pares y ocho ítems. Se observaron 24 coincidencias por modelo y variedad. La medida alcanzó su techo en ambos modelos; no demuestra equivalencia. Una respuesta puede incluir la cantidad esperada junto con otra alternativa, negar el resultado o incumplir parte de la instrucción. En una respuesta sobre tiempo de viaje, por ejemplo, se mencionaron tanto la duración esperada de un trayecto como el doble bajo un supuesto alternativo. La detección reconoce el marcador, pero la pertinencia de la alternativa necesita interpretación humana. Los otros doce ítems y las demás dimensiones quedan fuera de esta comprobación.

## Discusión y amenazas a la validez

La distribución por ítem muestra heterogeneidad. La media rioplatense frente al control de Luna pasó de +33,33 tokens en el corte previo de 288 respuestas a +22,00 en el corte actual. Esta variación evidencia dependencia de la composición del corpus. Los bloques añadidos incluyen cálculo y procedimiento; las comparaciones combinan selección de tareas y ventana de ejecución. Los 20 bloques carecen de una selección probabilística que permita extrapolar las cifras a los 60 ítems o a comunidades de hablantes.

La revisión documental encontró una amenaza concreta en I011. La consulta estándar exige verificar la copia «sin borrar los originales», mientras las tres variantes regionales solicitan copia y verificación sin expresar esa restricción. La clave compartida incluye conservar los originales. Una evaluación de comprensión podría penalizar de forma distinta restricciones que el usuario no enunció en todas las variantes. El hallazgo se registra para revisión humana y el ítem permanece en las tablas descriptivas. La anotación de rasgos también requiere revisión, como muestra I005, cuyo metadato léxico indica NONE y cuya formulación rioplatense contiene voseo.

VALUE y XNLIvar sustentan la importancia de validar las transformaciones antes de interpretar brechas de desempeño [11], [12]. El corte de DIALECTO-LLM añade evidencia de viabilidad técnica y una descripción del uso del servicio para este banco. La comparación de tokens puede orientar preguntas posteriores sobre condiciones de generación. La evaluación de precisión, comprensión y relevancia continúa ligada a la rúbrica. La presencia de un marcador alcanza un techo en todos los casos examinados y admite salidas con alternativas o condiciones, lo que limita su capacidad de discriminar respuestas.

El cegamiento es parcial porque los evaluadores ven la consulta original. La escala ordinal se resume mediante promedios por decisión del protocolo y necesita justificar su interpretación. Tres repeticiones ofrecen una descripción limitada de la variabilidad de generación. Los alias móviles, la ejecución por lotes y la latencia de red añaden incertidumbre sobre la estabilidad temporal. Los resultados del banco urbano tampoco representan la diversidad interna de países o regiones. Por ello, la presentación de resultados debe evitar jerarquizar comunidades a partir de los anclajes seleccionados.

## Objetivos específicos y avance

El documento de objetivos vincula cuatro entregables con los hitos H2 a H5 [1]. El Gantt [2, p. 2] añade la fundamentación (H1) y la divulgación (H6) y prevé tres sprints de dos semanas, seguimiento Kanban, revisión por otro integrante y supervisión docente.

Tabla 5. Objetivos específicos, plazos previstos y evidencia al corte [1].

| Hito previsto | Objetivo y estado al corte |
| --- | --- |
| H2 · Fin de semana 3 | Construir y validar 60 ítems pareados en cuatro formulaciones. Hay metadatos léxicos y anclajes. Queda por verificar equivalencia, naturalidad y anotación de rasgos por variante. |
| H3 · Fin de semana 4 | Consultar dos modelos por API con parámetros constantes, tres repeticiones y bitácora. Se registraron 480 de 1.440 respuestas en 20 ítems completos. |
| H4 · Fin de semana 5 | Aplicar la rúbrica de 1 a 5 a ciegas respecto de la variedad, calcular consistencia y verificar el acuerdo. Se prepararon las hojas. Quedan pendientes la calificación, el kappa y la consistencia. |
| H5 · Semana 6 | Contrastar cada variedad con el control por modelo y dimensión, con pruebas pareadas, intervalos, tamaños del efecto y ajuste de Holm-Bonferroni. Hay resultados exploratorios de uso y marcadores. El contraste de desempeño sigue pendiente. |

## Disponibilidad y reproducibilidad

Los análisis usan Python 3.12.10 y la biblioteca estándar. El PDF de lectura se genera con ReportLab a partir del mismo texto que produce la fuente IEEEtran. Los scripts, el banco y los documentos se distribuyen en el repositorio. Los registros de respuestas y las claves de evaluación se conservan localmente en runs/. Para verificar las cifras desde otro equipo se necesita acceso a esos registros. La huella de las respuestas de este corte es SHA-256 7363e78e1c411ecd682e5d7cdd15660b4f38fc46b47d4fca488289fa624e3fd7.

Para reproducir el corte, la guía [19] indica cómo consultar run-status, reconstruir la auditoría y generar los indicadores con la corrida original y el piloto. Los resúmenes registran la huella SHA-256 de las respuestas. Los JSONL, hojas, claves y tablas derivadas se conservan en runs/, fuera de Git. El script render_informe.py genera la fuente IEEEtran y el PDF de lectura desde el mismo texto.

La elaboración y revisión del código y del manuscrito recibieron asistencia de IA mediante Codex. Los subagentes revisaron coherencia, bibliografía y software. Las puntuaciones de las hojas siguen vacías y la responsabilidad de la aprobación académica y de la evaluación humana corresponde al equipo. El repositorio revisado carece de una licencia explícita, por lo que las condiciones de redistribución deben documentarse por sus titulares antes de una entrega pública de datos.

## Conclusión

El proyecto dispone de una cadena trazable desde el banco provisional hasta 480 respuestas de 20 ítems completos y sus tablas descriptivas. Se observó un incremento medio de 22,00 tokens de salida en Luna para rioplatense frente al estándar, con diferencias de signo y magnitud entre ítems. La validación del banco, el acuerdo entre evaluadores y las puntuaciones de desempeño son los pasos pendientes para abordar la pregunta principal. La revisión del corte permite especificar esos pendientes y corregir limitaciones del flujo de análisis antes de incorporar nuevas evaluaciones.

## Referencias

[1] Grupo 3, «Objetivos», documento del proyecto, p. 1.

[2] Grupo 3, «Metodología General del Proyecto DIALECTO-LLM», documento de metodología, pp. 1–2.

[3] Grupo 3, «Análisis comparativo del desempeño de modelos de lenguaje de gran escala frente a la variación dialectal del español», propuesta y estado del arte, pp. 1–8.

[4] S. L. Blodgett et al., «Language (Technology) is Power: A Critical Survey of “Bias” in NLP», ACL, 2020, pp. 5454–5476. DOI 10.18653/v1/2020.acl-main.485.

[5] J. Muñoz-Basols, M. del M. Palomares Marín y F. Moreno Fernández, «El Sesgo Lingüístico Digital (SLD) en la inteligencia artificial: implicaciones para los modelos de lenguaje masivos en español», Lengua y Sociedad, vol. 23, n.º 2, 2024. DOI 10.15381/lengsoc.v23i2.28665.

[6] M. Robles et al., «SESGO: Spanish Evaluation of Stereotypical Generative Outputs», AIES, vol. 8, n.º 3, 2025, pp. 2214–2226. DOI 10.1609/aies.v8i3.36707.

[7] C. España-Bonet y A. Barrón-Cedeño, «Elote, Choclo and Mazorca: on the Varieties of Spanish», NAACL, 2024, pp. 3689–3711. DOI 10.18653/v1/2024.naacl-long.204.

[8] M. Mayor-Rocher et al., «It's the same but not the same: Do LLMs distinguish Spanish varieties?», 2025. arXiv:2504.20049.

[9] Y. Kawasaki, «Evaluating Geographic Lexical Knowledge in Large Language Models Across 21 Spanish-Speaking Countries», preprint, 2026. arXiv:2602.09346v2.

[10] M. Grandury et al., «La Leaderboard: A Large Language Model Leaderboard for Spanish Varieties and Languages of Spain and Latin America», ACL, 2025, pp. 32482–32524. DOI 10.18653/v1/2025.acl-long.1561.

[11] J. Bengoetxea, I. Gonzalez-Dios y R. Agerri, «Lost in Variation? Evaluating NLI Performance in Basque and Spanish Geographical Variants», CoNLL, 2025, pp. 452–468. DOI 10.18653/v1/2025.conll-1.30.

[12] C. Ziems et al., «VALUE: Understanding Dialect Disparity in NLU», ACL, 2022, pp. 3701–3720. DOI 10.18653/v1/2022.acl-long.258.

[13] J. Oh et al., «DialectLLM: A Dialect-Aware Dialog[ue] Generation Framework Beyond Standard American English», preprint, 2026. arXiv:2601.24808v5.

[14] A. Yagubyan, «The Coin Flip Judge? Reliability and Bias in LLM-as-a-Judge Evaluation», preprint, 2026. arXiv:2606.13685.

[15] DIALECTO-LLM, «Protocolo de estudio, semana 1», docs/protocolo_semana1.tex.

[16] DIALECTO-LLM, «Diseño del banco y validación, semana 2», docs/diseno_banco_semana2.tex.

[17] DIALECTO-LLM, «Addendum de protocolo y bitácora de ejecución», 12 nov. 2026, docs/addendum_ejecucion_experimento.tex.

[18] SciPy, «wilcoxon», documentación de la prueba de rangos con signo, versión 1.18.0. https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html. Consultado el 12 nov. 2026.

[19] DIALECTO-LLM, «Análisis incremental y calificación independiente», src/ANALISIS.md.

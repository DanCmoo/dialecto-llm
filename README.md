# DIALECTO-LLM

Proyecto de evaluación pareada del desempeño de modelos de lenguaje ante variación dialectal del español. La planificación de semana 1 y el banco de consultas v2 de semana 2 se documentan en formato IEEE.

## Documentación

- [Informe del proyecto y resultados exploratorios](docs/informe_proyecto.pdf), con [fuente editable](docs/informe_proyecto.md) y [LaTeX IEEEtran](docs/informe_proyecto.tex). Documenta el corte de 288 respuestas, con la recolección detenida por RPD.
- [`docs/protocolo_semana1.pdf`](docs/protocolo_semana1.pdf) y su fuente [LaTeX](docs/protocolo_semana1.tex).
- [`docs/diseno_banco_semana2.pdf`](docs/diseno_banco_semana2.pdf) y su fuente [LaTeX](docs/diseno_banco_semana2.tex).

## Banco de consultas

- [`src/data/item_bank_v2.json`](src/data/item_bank_v2.json) es la versión de trabajo: 60 ítems y cuatro formulaciones dialectales por ítem.
- `item_bank_v1.json` y `item_bank_v1.csv` se conservan como línea base.
- [`src/data/validacion_hablantes_template.csv`](src/data/validacion_hablantes_template.csv) registra los espacios de revisión doble para las 240 variantes.

## Código

`src/dialectollm/` contiene la configuración, validadores y el planificador/ejecutor reanudable del estudio para OpenAI Responses API. El comando local se instala con:

```powershell
python -m pip install -e .
```

El plan offline no consume API. Ejecutar el piloto sí realiza llamadas facturables y requiere `OPENAI_API_KEY` en el entorno o en un archivo `.env` local y la opción explícita `--execute`. Puedes copiar `.env.example` como `.env` en la raíz del proyecto y pegar allí tu clave. `.env` está excluido por `.gitignore`; el ejemplo no contiene secretos. Los límites visibles del proyecto son por minuto y tokens; el código mantiene una salvaguarda local separada de 100 intentos por modelo en 24 horas. El piloto registra resultados en `runs/`, carpeta excluida de Git. No subas la clave API ni los artefactos de respuesta al repositorio público.

La configuración propone GPT-6 Luna y GPT-6.1 Terra con `medium`. El estudio completo son 1.440 respuestas en total e incluye los 144 resultados completados del piloto; quedan como máximo 1.296 llamadas nuevas. El calendario mantiene cada ítem completo y pareado: hasta cuatro ítems por lote (48 llamadas por modelo), con margen frente al RPD observado de 50. Consulta [src/README.md](src/README.md) para crear la corrida completa, integrar el piloto y reanudar cada lote.

`collection_ready=false` se mantiene hasta registrar la revisión lingüística independiente y la aprobación académica de la rúbrica y del plan de análisis. La corrida conserva esta condición como aviso en el manifiesto. La auditoría técnica y la descripción exploratoria están disponibles; el análisis confirmatorio de desempeño sigue pendiente de esos hitos y de las calificaciones humanas.

El informe actual distingue los objetivos y la metodología suministrados, las decisiones de ejecución y las desviaciones observadas. Los documentos de semanas 1 y 2 y el addendum conservan su valor histórico; sus modelos y conteos iniciales no sustituyen el manifiesto real ni el total de 1.440 respuestas, que incluye el piloto. Consulte la [revisión académica](docs/revision_academica.md) y los [comandos de actualización offline](src/ANALISIS.md).

Consulta [`src/README.md`](src/README.md) para los comandos y formatos de validación.

# DIALECTO-LLM

Proyecto de evaluación pareada del desempeño de modelos de lenguaje ante variación dialectal del español. La planificación de semana 1 y el banco de consultas v2 de semana 2 se documentan en formato IEEE.

## Documentación

- [`docs/protocolo_semana1.pdf`](docs/protocolo_semana1.pdf) y su fuente [LaTeX](docs/protocolo_semana1.tex).
- [`docs/diseno_banco_semana2.pdf`](docs/diseno_banco_semana2.pdf) y su fuente [LaTeX](docs/diseno_banco_semana2.tex).

## Banco de consultas

- [`src/data/item_bank_v2.json`](src/data/item_bank_v2.json) es la versión de trabajo: 60 ítems y cuatro formulaciones dialectales por ítem.
- `item_bank_v1.json` y `item_bank_v1.csv` se conservan como línea base.
- [`src/data/validacion_hablantes_template.csv`](src/data/validacion_hablantes_template.csv) registra los espacios de revisión doble para las 240 variantes.

## Código

`src/dialectollm/` contiene la configuración y validadores del estudio. El comando local se instala con:

```powershell
python -m pip install -e .
```

La recolección permanece bloqueada (`collection_ready=false`) hasta completar la revisión lingüística independiente, aprobar el protocolo académico y realizar el piloto de API y presupuesto. El código no hace llamadas a proveedores.

Consulta [`src/README.md`](src/README.md) para los comandos y formatos de validación.

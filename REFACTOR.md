# Spec: Refactor Dialectal de Banco de Preguntas

## Contexto
El archivo objetivo es `src/data/item_bank_v1.json`, el cual contiene un array de 60 objetos. Cada objeto tiene preguntas con claves de dialecto (`prompt_co`, `prompt_mx`, `prompt_rio`, `prompt_std`). Actualmente, los dialectos son demasiado similares (solo cambian palabras sueltas como "computador" vs "computadora").

## Objetivo
Reescribir las preguntas iterando sobre cada objeto del JSON para generar una diferenciación dialectal profunda (estructural, léxica y pragmática), asegurando que el formato JSON final sea completamente válido.

## Comportamiento del Agente (Pipeline de 3 Pasos)
Para cada uno de los 60 ítems en el JSON, debes aplicar mentalmente el siguiente pipeline antes de generar el resultado:

1. **Generador**: Crea 4 versiones de la idea central.
   - `prompt_std` (Neutro): Formal, técnico, procedimental. Sin regionalismos.
   - `prompt_co` (Colombiano): Uso estricto de "computador", sintaxis indirecta, uso del usted o impersonal (ej. "hacer un backup", "mirar si quedó bien").
   - `prompt_mx` (Mexicano): Uso de "compu", verbos como "respaldar", "checar", tono coloquial pero técnico.
   - `prompt_rio` (Rioplatense): Voseo explícito ("tenés", "querés"), términos como "pendrive", "fijarme", "armar", lenguaje directo.
2. **Evaluador**: Verifica que las oraciones tengan longitudes y estructuras asimétricas. Si la única diferencia es una palabra, descarta el intento.
3. **Refinador**: Exagera el rasgo dialectal y la estructura gramatical para asegurar la diferencia antes de escribir el output.

## Tarea de Ejecución
1. Lee y parsea el archivo `src/data/item_bank_v1.json`.
2. Itera secuencialmente sobre los 60 objetos aplicando el pipeline descrito.
3. Mantén intactos los IDs o cualquier otra metadata (categorías, tags) que ya exista en cada objeto; SOLO modifica los valores de las claves `prompt_co`, `prompt_mx`, `prompt_rio` y `prompt_std`.
4. Escribe el resultado final en `src/data/item_bank_v2.json` (no sobrescribas el v1 para tener control de cambios).

## Restricciones
- El archivo de salida DEBE ser un JSON válido, estructurado exactamente como el original.
- No uses comillas dobles dentro de las frases sin escaparlas correctamente (`\"`).tamente (`\"`).

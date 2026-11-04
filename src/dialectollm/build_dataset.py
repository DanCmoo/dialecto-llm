"""Build the v1 matched Spanish prompt bank from reviewed task specifications.

The regional wording is a controlled desk-review draft. Native-speaker review
is recorded as pending; this script never labels machine-generated variants as
linguistically validated.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "src" / "data" / "item_bank_v1.json"
CSV_OUTPUT = ROOT / "src" / "data" / "item_bank_v1.csv"
REVIEW_TEMPLATE = ROOT / "src" / "data" / "validacion_hablantes_template.csv"

LEXICON = {
    "BUS": {"co": "bus", "mx": "camión", "rio": "colectivo", "std": "autobús"},
    "COMPUTER": {"co": "computador", "mx": "computadora", "rio": "compu", "std": "equipo de cómputo"},
    "BEAN": {"co": "fríjoles", "mx": "frijoles", "rio": "porotos", "std": "frijoles secos"},
    "CHAT": {"co": "conversar", "mx": "platicar", "rio": "charlar", "std": "hablar"},
    "CAR": {"co": "carro", "mx": "coche", "rio": "auto", "std": "automóvil"},
}

# category, natural direct prompt, expected answer/criteria, controlled feature (or NONE)
SPECS = [
    # 1. Cálculo y comprensión factual estable
    ("calculo", "Un {BUS} tarda 12 minutos por trayecto. Si hago tres trayectos iguales, ¿cuánto tiempo de viaje acumulo?", "36 minutos; multiplicar 12 por 3.", "BUS"),
    ("calculo", "Un {CAR} consume 6 litros de combustible cada 100 km. ¿Cuántos litros consume en 250 km al mismo ritmo?", "15 litros; proporción directa: 6 x 2,5.", "CAR"),
    ("calculo", "Tengo 6 archivos de 750 KB cada uno en mi {COMPUTER}. ¿Cuántos KB ocupan en total, sin contar otros archivos?", "4500 KB; multiplicar 750 por 6.", "COMPUTER"),
    ("calculo", "Una receta usa 75 g de {BEAN} por persona. ¿Cuántos gramos necesito para cuatro personas?", "300 g; multiplicar 75 por 4.", "BEAN"),
    ("calculo", "Una reunión empieza a las 9:20 y dura 45 minutos. ¿A qué hora termina?", "A las 10:05.", "NONE"),
    ("calculo", "Una mezcla lleva ingredientes en proporción 2:5. Si preparo 14 unidades en total, ¿cuántas corresponden a la parte menor?", "4 unidades; hay 7 partes y cada una equivale a 2 unidades.", "NONE"),
    ("calculo", "Hay tres cajas con ocho cuadernos cada una. ¿Cuántos cuadernos hay en total?", "24 cuadernos.", "NONE"),
    ("calculo", "Un {BUS} recorre 12 km a una velocidad constante de 30 km/h. ¿Cuántos minutos tarda?", "24 minutos; 12/30 de hora.", "BUS"),
    ("calculo", "En tres días leo 18, 24 y 30 páginas. ¿Cuál es el promedio diario?", "24 páginas por día.", "NONE"),
    ("calculo", "Convierte 2,5 litros a mililitros. ¿Cuál es el resultado?", "2500 mililitros.", "NONE"),

    # 2. Procedimientos con condiciones explícitas
    ("procedimiento", "Tengo tres documentos guardados en mi {COMPUTER} y quiero hacer una copia de seguridad en una memoria externa. ¿Cómo compruebo que quedó bien?", "Incluir conectar la memoria, copiar los tres archivos y verificar apertura o tamaño; no borrar los originales.", "COMPUTER"),
    ("procedimiento", "Tengo 12 archivos y quiero ordenarlos en carpetas por año y tema, sin modificar su contenido. ¿Cómo puedo organizarlos en mi {COMPUTER}?", "Proponer carpetas por año/tema, mover/copiar archivos y comprobar ubicación; preservar el contenido.", "COMPUTER"),
    ("procedimiento", "Tengo que limpiar la pantalla de tu {COMPUTER}. ¿Qué cuidados debo tener? El equipo está apagado y desconectado.", "Apagar y desconectar; usar paño suave; aplicar producto al paño, no a la pantalla; secar sin presión excesiva.", "COMPUTER"),
    ("procedimiento", "Voy a preparar una lista de compras para cinco comidas. ¿Cómo junto los ingredientes de las recetas y reviso que no repita productos?", "Extraer ingredientes, sumar cantidades, unificar duplicados y revisar la lista; no inventar ingredientes.", "NONE"),
    ("procedimiento", "Quiero guardar en mi {COMPUTER} una copia de las fotos de mi celular. ¿Cómo compruebo que las fotos copiadas se abren?", "Conectar o transferir, guardar la copia y comprobar que abre; conservar las fotos originales hasta verificarla.", "COMPUTER"),
    ("procedimiento", "¿Me das cinco pasos para precalentar el horno a 180 °C y hornear una preparación durante 20 minutos? Incluye una precaución de seguridad.", "Seleccionar 180 °C, esperar precalentamiento, introducir la preparación, controlar 20 min y usar protección al retirar.", "NONE"),
    ("procedimiento", "Somos dos personas y tenemos cuatro tareas domésticas. ¿Qué reparto nos sugieres para que cada quien haga dos tareas distintas?", "Asignar cuatro tareas distintas, dos por persona; cualquier reparto válido.", "NONE"),
    ("procedimiento", "Tengo que dividir 24 {BEAN} en seis porciones iguales. ¿Cuánto va en cada una y cómo compruebo el reparto?", "Cuatro unidades por porción; sumar o multiplicar 6 por 4 para comprobar.", "BEAN"),
    ("procedimiento", "Quiero {CHAT} con un compañero para acordar cuándo reunirnos, pero tenemos horarios distintos. ¿Cómo encontramos un momento que nos sirva a ambos?", "Proponer compartir disponibilidad, comparar horarios y confirmar una fecha común con respeto.", "CHAT"),
    ("procedimiento", "Voy a instalar una aplicación desde la tienda oficial del celular. ¿Qué debería revisar en los permisos antes de abrirla?", "Usar tienda oficial, comprobar nombre/desarrollador, instalar, revisar permisos y rechazar los innecesarios.", "NONE"),

    # 3. Explicación
    ("explicacion", "¿Por qué el hielo suele flotar en agua líquida? Responde en dos o tres frases.", "Porque el hielo tiene menor densidad que el agua líquida, debido a la estructura que forma al congelarse.", "NONE"),
    ("explicacion", "Estoy pensando en guardar una copia de un archivo importante en otro dispositivo, como mi {COMPUTER}. ¿Qué ventaja tiene hacerlo?", "Reduce el riesgo de perderlo si falla o se pierde el dispositivo original; una copia debe verificarse.", "COMPUTER"),
    ("explicacion", "¿Por qué hacer pausas breves puede ayudar durante una sesión larga de estudio?", "Puede reducir fatiga y ayudar a recuperar atención; no afirmar que garantiza aprendizaje.", "NONE"),
    ("explicacion", "Explica por qué dos mediciones de la misma longitud pueden diferir ligeramente.", "Resolución del instrumento, calibración, técnica y condiciones de medición producen incertidumbre.", "NONE"),
    ("explicacion", "¿Cuál es la diferencia entre promedio aritmético y mediana? Incluye un ejemplo breve.", "Promedio: suma/n; mediana: valor central ordenado; un ejemplo coherente que muestre que pueden diferir.", "NONE"),
    ("explicacion", "¿Para qué sirve escribir un esquema antes de redactar un informe?", "Ayuda a ordenar ideas, anticipar secciones y mantener una secuencia lógica; no sustituye la revisión.", "NONE"),
    ("explicacion", "¿Qué le puede pasar a una botella llena de agua si se congela? ¿Por qué?", "El agua aumenta de volumen al congelarse y puede ejercer presión sobre el recipiente.", "NONE"),
    ("explicacion", "Describe brevemente cómo se forman gotas de agua en el exterior de un vaso frío.", "El vapor de agua del aire se enfría al tocar la superficie y se condensa en líquido.", "NONE"),
    ("explicacion", "¿Por qué es importante instalar actualizaciones de seguridad en tu {COMPUTER}?", "Pueden corregir vulnerabilidades y errores; se recomienda respaldo y fuente oficial, sin prometer seguridad total.", "COMPUTER"),
    ("explicacion", "Distingue una afirmación factual de una opinión e incluye un ejemplo de cada una.", "Un hecho se puede contrastar con evidencia; una opinión expresa valoración. Ejemplos correctamente clasificados.", "NONE"),

    # 4. Recomendación bajo restricciones dadas
    ("recomendacion", "Tengo dos opciones de {BUS}: la A tarda 20 minutos y cuesta 8 unidades; la B tarda 35 minutos y cuesta 5. Si priorizo llegar más rápido y acepto pagar hasta 10, ¿cuál conviene y por qué?", "La A: cumple el tope de 10 y tarda menos.", "BUS"),
    ("recomendacion", "Necesito elegir entre dos opciones de {COMPUTER} para escribir documentos y navegar: una cuesta 450 unidades y la otra 620. Mi presupuesto máximo es 500; ¿cuál opción cumple el presupuesto?", "La opción de 450; indicar que las necesidades de uso se cumplen solo si las especificaciones lo permiten, dato no dado.", "COMPUTER"),
    ("recomendacion", "Tengo tres tareas: una vence hoy y dura 20 minutos; otra vence mañana y dura una hora; la tercera no tiene fecha y dura 15 minutos. ¿Qué orden inicial recomiendas?", "Priorizar la que vence hoy; después planificar la de mañana; la tercera puede ir después, explicando que depende de otros compromisos.", "NONE"),
    ("recomendacion", "Para una receta de seis personas necesito 450 g de {BEAN}, pero solo tengo 300 g. ¿Qué ajuste proporcional sugieres?", "Preparar dos tercios de la receta, para cuatro porciones; escalar los demás ingredientes igual.", "BEAN"),
    ("recomendacion", "Quiero {CHAT} con una persona para resolver un desacuerdo de trabajo. Sugiere una apertura respetuosa de una frase y una pregunta para conocer su perspectiva.", "Una frase no acusatoria y una pregunta abierta; no asumir quién tiene la razón.", "CHAT"),
    ("recomendacion", "Debo elegir entre un {CAR} que cuesta 9000 unidades y otro que cuesta 10500. Mi límite es 10000 y solo importa cumplirlo. ¿Cuál opción es válida?", "Solo el de 9000; no inferir otras características.", "CAR"),
    ("recomendacion", "Tengo 30 minutos antes de salir y tres pendientes que duran 10, 15 y 20 minutos. ¿Qué combinación completa exactamente en ese tiempo?", "Las tareas de 10 y 20 minutos suman 30; también puede señalar que la de 15 no cabe junto a ninguna otra.", "NONE"),
    ("recomendacion", "Para recorrer 4 km puedo caminar a 4 km/h o usar un {BUS} que tarda 18 minutos en total. Si el criterio es llegar antes, ¿qué opción conviene?", "El bus: 18 min frente a 60 min caminando; explicar cálculo.", "BUS"),
    ("recomendacion", "Tengo 8 porciones de {BEAN} y cuatro recipientes. ¿Cómo las repartirías para que cada recipiente tenga lo mismo?", "Dos porciones por recipiente.", "BEAN"),
    ("recomendacion", "Necesito {CHAT} durante 10 minutos con una colega y ambos tenemos una agenda compartida. ¿Qué método simple recomiendas para encontrar un horario común?", "Comparar espacios disponibles, proponer una franja y confirmarla; no suponer acceso a la agenda sin permiso.", "CHAT"),

    # 5. Resumen de textos originales del estudio
    ("resumen", "¿Me resumes esto en una frase? «El taller empieza a las 10:00. El {BUS} A tarda 15 minutos y el B tarda 25. Para llegar antes, conviene salir con tiempo». ", "El taller inicia a las 10; A tarda menos que B y conviene prever margen para llegar.", "BUS"),
    ("resumen", "¿Me resumes esto en una frase? «El equipo guardó los documentos en su {COMPUTER}, hizo una copia en un dispositivo externo y abrió dos archivos para comprobarla». ", "Se hizo una copia externa de los documentos y se verificó abriendo archivos.", "COMPUTER"),
    ("resumen", "¿Me resumes esto en una frase? «La receta lleva 300 g de {BEAN}. Como ahora comerán cuatro personas en vez de seis, ajustaron todas las cantidades a dos tercios». ", "La receta de seis porciones se redujo proporcionalmente a cuatro, usando 300 g de fríjoles/porotos.", "BEAN"),
    ("resumen", "¿Me resumes esto en una frase? «El grupo decidió {CHAT} el lunes para revisar el borrador. Antes, cada integrante enviará sus observaciones y luego acordarán los cambios». ", "El equipo hablará el lunes sobre el borrador y usará observaciones previas para acordar cambios.", "CHAT"),
    ("resumen", "¿Me resumes esto en una frase? «El {CAR} recorrió 120 km en dos horas. El registro no dice si hizo paradas ni cuánta gasolina usó». ", "El carro/auto recorrió 120 km en dos horas; el texto no reporta paradas ni consumo.", "CAR"),
    ("resumen", "Resume en una frase: «Se compararon tres métodos con la misma lista de tareas. El método X terminó primero, pero el método Y tuvo menos errores; el equipo debe decidir qué criterio prioriza». ", "X fue más rápido y Y cometió menos errores; falta elegir qué criterio importa más.", "NONE"),
    ("resumen", "Resume en una frase: «La planta recibió 200 ml de agua el lunes y el jueves. Durante la semana estuvo cerca de una ventana, pero no se midió la luz ni se registró el crecimiento». ", "La planta se regó dos veces con 200 ml y estuvo junto a una ventana, sin datos de luz o crecimiento.", "NONE"),
    ("resumen", "Resume en una frase: «La reunión estaba prevista para las 14:00, duró 45 minutos y terminó con tres tareas asignadas a distintas personas». ", "La reunión de las 14:00 duró 45 minutos y dejó tres tareas asignadas.", "NONE"),
    ("resumen", "Resume en una frase: «El informe presenta primero la pregunta, luego describe los datos y al final compara los resultados. La sección de limitaciones todavía está pendiente». ", "El informe ordena pregunta, datos y resultados, pero aún falta redactar las limitaciones.", "NONE"),
    ("resumen", "Resume en una frase: «Para reducir errores, dos personas revisaron la tabla por separado. Encontraron cuatro diferencias y las resolvieron consultando los registros originales». ", "Dos revisores compararon la tabla, detectaron cuatro discrepancias y las resolvieron con los originales.", "NONE"),

    # 6. Razonamiento y resolución de problemas
    ("razonamiento", "El {BUS} sale cada 20 minutos desde las 8:00. Si llego a la parada a las 8:07 y el servicio mantiene el horario, ¿a qué hora sale el siguiente?", "A las 8:20; explicar que la salida de 8:00 ya pasó.", "BUS"),
    ("razonamiento", "Tengo 120 unidades. Compro dos cuadernos de 35 cada uno y un lápiz de 12. ¿Cuánto dinero me queda?", "38 unidades.", "NONE"),
    ("razonamiento", "Una caja tiene 18 piezas. Se usan un tercio y luego se agregan 4 piezas nuevas. ¿Cuántas hay ahora?", "16 piezas: se usan 6, quedan 12 y se agregan 4.", "NONE"),
    ("razonamiento", "Todos los archivos de la carpeta A de tu {COMPUTER} son copias; el archivo X está en esa carpeta. ¿Qué se puede concluir sobre X?", "X es una copia, según las premisas; no se sabe de qué archivo es copia.", "COMPUTER"),
    ("razonamiento", "Una persona afirma: «Todos los grupos que terminaron temprano tuvieron cuatro integrantes. Nuestro grupo tiene cuatro integrantes, por lo tanto terminará temprano». ¿La conclusión se sigue necesariamente? Explica.", "No; afirmar que terminar temprano implica cuatro integrantes no permite inferir la inversa.", "NONE"),
    ("razonamiento", "En una lista, Ana aparece antes que Bruno y Bruno antes que Carla. ¿Qué orden relativo se deduce entre Ana y Carla?", "Ana aparece antes que Carla, por transitividad.", "NONE"),
    ("razonamiento", "Un depósito tenía 50 litros. Se retiran 12 por la mañana y 9 por la tarde; luego se agregan 15. ¿Cuánto queda?", "44 litros.", "NONE"),
    ("razonamiento", "El {CAR} A tarda 30 minutos y el B 45. A sale a las 9:10 y B a las 9:00. ¿Cuál llega primero si no hay retrasos?", "A llega a 9:40; B llega a 9:45; llega primero A.", "CAR"),
    ("razonamiento", "Necesito enviar un archivo hoy, revisar otro mañana y {CHAT} con el equipo el viernes. Hoy es jueves. ¿Qué pendiente debe atenderse primero por fecha?", "Enviar el archivo hoy; después revisar el de mañana y reunirse el viernes.", "CHAT"),
    ("razonamiento", "Una mesa tiene capacidad para 6 personas. Llegan grupos indivisibles de 2, 3 y 2. Si se puede elegir qué grupos se sientan juntos, ¿cuál es el mínimo de personas que debe esperar?", "Dos personas: se sientan juntos los grupos de 2 y 3 (5 personas). No es posible sentar a los tres grupos (7 personas).", "NONE"),
]

DIALECTS = ("co", "mx", "rio", "std")

# Adaptación verbal rioplatense preliminar, limitada a formas explícitas de
# segunda persona; debe pasar la misma revisión humana que el léxico.
RIO_VERBS = {
    "Convierte": "Convertí", "Explica": "Explicá", "Describe": "Describí",
    "Propón": "Proponé", "Indica": "Indicá", "Resume": "Resumí",
    "Distingue": "Distinguí", "recomiendas": "recomendás",
    "sugieres": "sugerís", "resumes": "resumís",
}


def build() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for index, (category, body, key, feature) in enumerate(SPECS, start=1):
        if feature != "NONE" and "{" + feature + "}" not in body:
            raise ValueError(f"I{index:03d}: falta el marcador para el rasgo {feature}.")
        prompts = {}
        for dialect in DIALECTS:
            rendered = body
            if feature != "NONE":
                rendered = rendered.replace("{" + feature + "}", LEXICON[feature][dialect])
            if dialect == "rio":
                for source, target in RIO_VERBS.items():
                    rendered = rendered.replace(source, target)
            prompts[dialect] = rendered.strip()
        records.append({
            "item_id": f"I{index:03d}",
            "category": category,
            "task": "evaluacion_textual",
            "prompt_co": prompts["co"],
            "prompt_mx": prompts["mx"],
            "prompt_rio": prompts["rio"],
            "prompt_std": prompts["std"],
            "answer_key": key,
            "lexical_feature": feature,
            "register": "urbano_conversacional_no_estereotipado",
            "anchor": {"co": "Bogota", "mx": "Ciudad de Mexico", "rio": "Buenos Aires", "std": "espanol_panhispanico_neutro"},
            "review_status": "borrador_revision_documental; revision_hablante_nativo_pendiente",
            "review_note": "Equivalencia propuesta por anclajes semanticos y sustitucion controlada; validar naturalidad y comprension con hablantes antes del piloto.",
        })
    return records


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    records = build()
    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_fields = ["item_id", "category", "task", "prompt_co", "prompt_mx",
                  "prompt_rio", "prompt_std", "answer_key", "lexical_feature",
                  "anchor_co", "anchor_mx", "anchor_rio", "anchor_std", "review_status"]
    with CSV_OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=csv_fields)
        writer.writeheader()
        for item in records:
            row = {key: item[key] for key in csv_fields if key in item}
            for dialect in DIALECTS:
                row[f"anchor_{dialect}"] = item["anchor"][dialect]
            writer.writerow(row)
    with REVIEW_TEMPLATE.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[
            "item_id", "dialect", "anchor", "reviewer_slot", "reviewer_id", "native_or_expert",
            "naturalness_1_5", "meaning_equivalence_1_5", "issue_tags",
            "suggested_revision", "approved_for_pilot",
        ])
        writer.writeheader()
        for item in records:
            for dialect in DIALECTS:
                for reviewer_slot in (1, 2):
                    writer.writerow({
                        "item_id": item["item_id"], "dialect": dialect,
                        "anchor": item["anchor"][dialect], "reviewer_slot": reviewer_slot,
                        "reviewer_id": "", "native_or_expert": "", "naturalness_1_5": "",
                        "meaning_equivalence_1_5": "", "issue_tags": "",
                        "suggested_revision": "", "approved_for_pilot": "",
                    })
    print(f"Banco generado: {len(records)} ítems x 4 variedades = {len(records) * 4} formulaciones")
    print(f"Archivo: {OUTPUT}")
    print(f"CSV legible: {CSV_OUTPUT}")
    print(f"Plantilla de revisión: {REVIEW_TEMPLATE}")


if __name__ == "__main__":
    main()

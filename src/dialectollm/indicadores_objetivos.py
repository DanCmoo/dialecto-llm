"""Análisis exploratorio sin red sobre una instantánea local de DIALECTO-LLM."""

from __future__ import annotations

import argparse
import json
import re
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median

if __package__:
    from .analysis import analysis_lock, audit_run, csvwrite, jsonwrite, verify_sources
else:
    from analysis import analysis_lock, audit_run, csvwrite, jsonwrite, verify_sources


# Selección por clave: magnitudes u horas únicas en los ítems observados.
# Evalúa presencia del marcador, no corrección semántica de la respuesta.
MARCADORES = {
    "I001": ("36 minutos", r"36\s*(?:minutos?|min)"),
    "I002": ("15 litros", r"15\s*(?:litros?|l)"),
    "I003": ("4500 KB", r"4[. ]?500\s*kb"),
    "I004": ("300 g", r"300\s*(?:gramos?|g)"),
    "I005": ("10:05", r"10\s*:\s*05"),
    "I006": ("4 unidades", r"4\s*unidades?"),
    "I007": ("24 cuadernos", r"24\s*cuadernos?"),
    "I051": ("8:20", r"0?8\s*:\s*20"),
}


def marcador_presente(texto: str, patron: str) -> bool:
    plano = unicodedata.normalize("NFKC", texto).casefold()
    plano = plano.replace("*", "").replace("`", "").replace("\u2212", "-")
    # La puntuación puede cerrar la respuesta, pero no debe cortar decimales.
    return re.search(rf"(?<![\w+\-])(?<!\d[.,:])(?:{patron})(?!\w|[.,:]\d)", plano) is not None


def medidas(respuesta: dict) -> dict:
    uso = respuesta["usage"]
    salida = uso["output_tokens"]
    razonamiento = uso["output_tokens_details"]["reasoning_tokens"]
    latencia = respuesta["latency_ms"]
    if (isinstance(latencia, bool) or not isinstance(latencia, (int, float))
            or not math.isfinite(latencia) or latencia < 0):
        raise ValueError("Latencia inválida en una respuesta completada.")
    return {
        "tokens_entrada": uso["input_tokens"],
        "tokens_salida": salida,
        "tokens_razonamiento": razonamiento,
        "tokens_salida_menos_razonamiento": salida - razonamiento,
        "caracteres": len(respuesta["output_text"]),
        "latencia_ms": latencia,
        "costo_estimado_usd": respuesta["estimated_cost_usd"],
    }


def resumen_pareado(pares: list[dict], campos: list[str]) -> dict:
    por_item = defaultdict(list)
    for par in pares:
        por_item[par["item"]].append(par)
    resultado = {"items": len(por_item), "pares": len(pares), "medidas": {}}
    if not pares:
        return resultado
    for campo in campos:
        diferencias = [
            mean(par[f"{campo}_b_menos_a"] for par in filas)
            for filas in por_item.values()
        ]
        retirar_uno = [
            mean(diferencias[:i] + diferencias[i + 1 :])
            for i in range(len(diferencias))
        ] if len(diferencias) > 1 else []
        resultado["medidas"][campo] = {
            "media_a": mean(mean(par[f"{campo}_a"] for par in filas) for filas in por_item.values()),
            "media_b": mean(mean(par[f"{campo}_b"] for par in filas) for filas in por_item.values()),
            "media_b_menos_a": mean(diferencias),
            "mediana_b_menos_a": median(diferencias),
            "items_con_b_menor": sum(delta < 0 for delta in diferencias),
            "items_con_b_mayor": sum(delta > 0 for delta in diferencias),
            "items_empatados": sum(delta == 0 for delta in diferencias),
            "intervalo_sensibilidad_retirar_un_item": (
                [min(retirar_uno), max(retirar_uno)] if retirar_uno else None
            ),
        }
    return resultado


def contrastes_control(
    pares: list[dict], campos: list[str], modelos: list[str], variedades: list[str], control: str
) -> dict:
    base = {
        (par["item"], par["replica"]): par
        for par in pares
        if par["variedad"] == control
    }
    resultado = {}
    for lado, modelo in zip(("a", "b"), modelos):
        resultado[modelo] = {}
        for variedad in variedades:
            if variedad == control:
                continue
            pares_control = []
            for par in pares:
                if par["variedad"] != variedad:
                    continue
                referencia = base[par["item"], par["replica"]]
                fila = {"item": par["item"]}
                for campo in campos:
                    fila[f"{campo}_a"] = referencia[f"{campo}_{lado}"]
                    fila[f"{campo}_b"] = par[f"{campo}_{lado}"]
                    fila[f"{campo}_b_menos_a"] = fila[f"{campo}_b"] - fila[f"{campo}_a"]
                pares_control.append(fila)
            resultado[modelo][variedad] = resumen_pareado(pares_control, campos)
    return {"lado_a": control, "lado_b": "variedad", "por_modelo": resultado}


def analizar_instantanea(run: Path) -> dict:
    audit = audit_run(run)
    if audit["problems"]:
        raise ValueError(f"La auditoría detectó {len(audit['problems'])} incidencias. Ejecute analysis.py y revise incidencias.csv.")
    manifest = audit["manifest"]
    banco = audit["bank"]
    modelos = [modelo["alias"] for modelo in manifest["models"]]
    variedades = manifest["dialects"]
    control = audit["config"]["control_dialect"]
    if control not in variedades:
        raise ValueError("La variedad de control no consta en el manifiesto.")
    esperadas = {
        (variedad, replica, modelo)
        for variedad in variedades
        for replica in range(1, manifest["repetitions"] + 1)
        for modelo in modelos
    }
    por_item = defaultdict(dict)
    for fila in audit["complete"].values():
        coordenada = (fila["dialect"], fila["replicate"], fila["model_alias"])
        por_item[fila["item_id"]][coordenada] = fila

    items_completos = sorted(item for item, bloque in por_item.items() if esperadas == bloque.keys())
    pares = []
    verificaciones = []
    campos_medidas = ["tokens_entrada", "tokens_salida", "tokens_razonamiento",
                      "tokens_salida_menos_razonamiento", "caracteres", "latencia_ms", "costo_estimado_usd"]
    for item in items_completos:
        bloque = por_item[item]
        piloto = {bool(fila.get("reused_from_pilot")) for fila in bloque.values()}
        if len(piloto) != 1:
            raise ValueError(f"Procedencia mixta dentro de un ítem completo: {item}.")
        cohorte = "piloto_reutilizado" if piloto == {True} else "recoleccion_adicional"
        for variedad in variedades:
            for replica in range(1, manifest["repetitions"] + 1):
                a, b = [bloque[variedad, replica, modelo] for modelo in modelos]
                clave = {"item": item, "variedad": variedad, "replica": replica, "cohorte": cohorte}
                ma, mb = medidas(a), medidas(b)
                par = dict(clave)
                for campo in campos_medidas:
                    par[f"{campo}_a"] = ma[campo]
                    par[f"{campo}_b"] = mb[campo]
                    par[f"{campo}_b_menos_a"] = mb[campo] - ma[campo]
                pares.append(par)
                if item in MARCADORES:
                    etiqueta, patron = MARCADORES[item]
                    if not marcador_presente(banco[item]["answer_key"], patron):
                        raise ValueError(f"El marcador de {item} difiere de la clave congelada.")
                    verificaciones.append({
                        **clave,
                        "marcador_de_clave": etiqueta,
                        "a_presente": int(marcador_presente(a["output_text"], patron)),
                        "b_presente": int(marcador_presente(b["output_text"], patron)),
                    })

    resultado = {
        "sha256_respuestas": audit["response_hash"],
        "estado_validacion": "valido",
        "sha256_banco": manifest["input_hashes"]["bank_sha256"],
        "modelos": {"a": modelos[0], "b": modelos[1]},
        "items_completos": items_completos,
        "items_con_respuestas_incompletos": sorted(por_item.keys() - set(items_completos)),
        "categorias": dict(Counter(banco[item]["category"] for item in items_completos)),
        "pareado": resumen_pareado(pares, campos_medidas),
        "por_variedad": {
            variedad: resumen_pareado([p for p in pares if p["variedad"] == variedad], campos_medidas)
            for variedad in variedades
        },
        "contrastes_control": contrastes_control(pares, campos_medidas, modelos, variedades, control),
        "por_cohorte": {
            cohorte: resumen_pareado([p for p in pares if p["cohorte"] == cohorte], campos_medidas)
            for cohorte in ("piloto_reutilizado", "recoleccion_adicional")
        },
        "por_item": {
            item: resumen_pareado([p for p in pares if p["item"] == item], campos_medidas)
            for item in items_completos
        },
        "marcadores": {
            "items": sorted({fila["item"] for fila in verificaciones}),
            "pares": len(verificaciones),
            "a_presente": sum(fila["a_presente"] for fila in verificaciones),
            "b_presente": sum(fila["b_presente"] for fila in verificaciones),
            "ambos_presentes": sum(fila["a_presente"] and fila["b_presente"] for fila in verificaciones),
        },
    }
    salida = run / "analisis"
    salida.mkdir(exist_ok=True)
    verify_sources(audit["sources"])
    campos_pares = ["item", "variedad", "replica", "cohorte"] + [
        f"{campo}_{sufijo}" for campo in campos_medidas for sufijo in ("a", "b", "b_menos_a")
    ]
    csvwrite(salida / "indicadores_pares.csv", campos_pares, pares)
    csvwrite(
        salida / "marcadores_numericos.csv",
        ["item", "variedad", "replica", "cohorte", "marcador_de_clave", "a_presente", "b_presente"],
        verificaciones,
    )
    jsonwrite(salida / "indicadores_objetivos.json", resultado)
    return resultado


def analizar(run: Path) -> dict:
    run = Path(run)
    salida = run / "analisis"
    salida.mkdir(exist_ok=True)
    resumen = salida / "indicadores_objetivos.json"
    with analysis_lock(salida):
        jsonwrite(resumen, {"estado_validacion": "en_proceso"})
        try:
            return analizar_instantanea(run)
        except Exception as exc:
            jsonwrite(resumen, {"estado_validacion": "error", "error": str(exc)})
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="directorio local de la corrida")
    resultado = analizar(parser.parse_args().run)
    compacto = {campo: resultado[campo] for campo in ("modelos", "pareado", "marcadores")}
    print(json.dumps(compacto, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

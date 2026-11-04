"""Load and validate study configuration and rating CSV files."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

EXPECTED_DIALECTS = {"co", "mx", "rio", "std"}
EXPECTED_DIMENSIONS = {"precision", "comprehension", "relevance"}
RATING_COLUMNS = {
    "response_id", "item_id", "dialect", "model_alias", "replicate",
    "dimension", "rater_id", "score",
}


class ValidationError(ValueError):
    """Raised when a config or data file does not satisfy the study contract."""


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        config = json.load(stream)
    if not isinstance(config, dict):
        raise ValidationError("La raíz de la configuración debe ser un objeto JSON.")
    return config


def validate_item_bank(path: str | Path, config: dict[str, Any]) -> dict[str, int]:
    """Validate the v1 item bank's IDs, strata, prompt variants, and answer keys."""
    validate_config(config)
    with Path(path).open("r", encoding="utf-8-sig") as stream:
        items = json.load(stream)
    if not isinstance(items, list):
        raise ValidationError("El banco debe ser una lista JSON.")
    expected_ids = {f"I{i:03d}" for i in range(1, config["items"] + 1)}
    ids = [item.get("item_id") for item in items]
    if len(items) != config["items"] or set(ids) != expected_ids or len(set(ids)) != len(ids):
        raise ValidationError("El banco debe tener IDs únicos y consecutivos I001-I060.")
    distribution: dict[str, int] = {}
    for item in items:
        category = item.get("category")
        distribution[category] = distribution.get(category, 0) + 1
        if not item.get("answer_key", "").strip():
            raise ValidationError(f"{item['item_id']}: falta answer_key.")
        for dialect, suffix in (("co", "co"), ("mx", "mx"), ("rio", "rio"), ("std", "std")):
            prompt = item.get(f"prompt_{suffix}", "")
            if not prompt.strip() or "{" in prompt or "}" in prompt:
                raise ValidationError(f"{item['item_id']}/{dialect}: formulación vacía o con plantilla sin resolver.")
            if dialect not in item.get("anchor", {}):
                raise ValidationError(f"{item['item_id']}: falta el anclaje dialectal {dialect}.")
        if "pendiente" not in item.get("review_status", ""):
            raise ValidationError(f"{item['item_id']}: no debe afirmarse revisión nativa inexistente.")
    expected_distribution = config.get("item_categories", {})
    if distribution != expected_distribution:
        raise ValidationError(f"Distribución de categorías no coincide: {distribution}.")
    return {"items": len(items), "variants": len(items) * len(config["dialects"]),
            "categories": len(distribution)}


def validate_language_review_template(path: str | Path, *, require_complete: bool = False) -> dict[str, int]:
    """Check 2-reviewer slots for every item and dialect; optionally require approval."""
    required = {"item_id", "dialect", "reviewer_slot", "reviewer_id", "native_or_expert",
                "naturalness_1_5", "meaning_equivalence_1_5", "approved_for_pilot"}
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if required - set(reader.fieldnames or []):
            raise ValidationError("La plantilla de revisión lingüística no tiene las columnas requeridas.")
        rows = list(reader)
    expected = {(f"I{i:03d}", dialect, str(slot))
                for i in range(1, 61) for dialect in EXPECTED_DIALECTS for slot in (1, 2)}
    actual = {(row["item_id"], row["dialect"], row["reviewer_slot"]) for row in rows}
    if len(rows) != len(expected) or actual != expected:
        raise ValidationError("Se requieren 480 espacios de revisión únicos (60 ítems × 4 variantes × 2 revisores).")
    if require_complete:
        reviewers_by_pair: dict[tuple[str, str], set[str]] = {}
        for row in rows:
            if not row["reviewer_id"].strip() or row["native_or_expert"].strip().lower() not in {"si", "sí", "yes", "true"}:
                raise ValidationError(f"{row['item_id']}/{row['dialect']}: falta identificación de revisor nativo/experto.")
            pair = (row["item_id"], row["dialect"])
            reviewers_by_pair.setdefault(pair, set()).add(row["reviewer_id"].strip())
            try:
                naturalness = int(row["naturalness_1_5"])
                equivalence = int(row["meaning_equivalence_1_5"])
            except ValueError as exc:
                raise ValidationError(f"{row['item_id']}/{row['dialect']}: faltan puntuaciones 1-5.") from exc
            if not (1 <= naturalness <= 5 and 1 <= equivalence <= 5):
                raise ValidationError(f"{row['item_id']}/{row['dialect']}: las puntuaciones deben estar entre 1 y 5.")
            if naturalness < 4 or equivalence < 4:
                raise ValidationError(f"{row['item_id']}/{row['dialect']}: ambas puntuaciones deben ser al menos 4 para aprobar.")
            if row["approved_for_pilot"].strip().lower() not in {"si", "sí", "yes", "true"}:
                raise ValidationError(f"{row['item_id']}/{row['dialect']}: variante no aprobada para piloto.")
        repeated_pairs = [pair for pair, reviewers in reviewers_by_pair.items() if len(reviewers) != 2]
        if repeated_pairs:
            item_id, dialect = repeated_pairs[0]
            raise ValidationError(f"{item_id}/{dialect}: se requieren dos revisores distintos.")
    return {"review_slots": len(rows), "item_dialect_pairs": len(rows) // 2}


def validate_config(config: dict[str, Any], *, require_models: bool = False) -> list[str]:
    """Check design invariants. Return warnings; raise on structural violations."""
    errors: list[str] = []
    warnings: list[str] = []

    if config.get("study_id") != "DIALECTO-LLM":
        errors.append("study_id debe ser DIALECTO-LLM.")
    if config.get("items") != 60:
        errors.append("El diseño aprobado requiere exactamente 60 ítems.")
    if set(config.get("dialects", [])) != EXPECTED_DIALECTS or len(config.get("dialects", [])) != 4:
        errors.append("dialects debe contener co, mx, rio y std una sola vez.")
    if config.get("control_dialect") != "std":
        errors.append("control_dialect debe ser std.")
    if config.get("repetitions") != 3:
        errors.append("El diseño requiere tres repeticiones por combinación.")
    if set(config.get("dimensions", [])) != EXPECTED_DIMENSIONS:
        errors.append("dimensions debe contener precision, comprehension y relevance.")
    if config.get("score_min") != 1 or config.get("score_max") != 5:
        errors.append("La escala prevista debe ser ordinal de 1 a 5.")

    models = config.get("models", [])
    if len(models) != 2:
        errors.append("Deben declararse exactamente dos modelos.")
    else:
        aliases = [model.get("alias") for model in models]
        if len(set(aliases)) != 2 or None in aliases:
            errors.append("Los dos alias de modelo deben ser distintos y no vacíos.")
        missing = [model.get("alias", "?") for model in models
                   if not all(model.get(key) for key in ("provider", "model_id", "snapshot"))]
        if missing:
            message = "Faltan proveedor, model_id o snapshot para: " + ", ".join(missing)
            if require_models:
                errors.append(message)
            else:
                warnings.append(message)

    if require_models and config.get("collection_ready") is not True:
        errors.append("collection_ready debe ser true tras revisión lingüística, aprobación académica y piloto.")
    elif config.get("collection_ready") is not True:
        warnings.append("La recolección sigue bloqueada hasta completar revisión lingüística, aprobación académica y piloto.")

    if errors:
        raise ValidationError("\n".join(errors))
    return warnings


def validate_ratings_csv(
    path: str | Path,
    config: dict[str, Any],
    *,
    require_complete: bool = True,
    minimum_raters: int = 2,
) -> dict[str, int]:
    """Validate score rows and (by default) full response/dimension coverage.

    Expected one row per evaluator, response, and dimension. The raw model
    response itself is stored separately; this file contains ratings only.
    """
    validate_config(config, require_models=True)
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or [])
        missing = RATING_COLUMNS - headers
        if missing:
            raise ValidationError("Faltan columnas: " + ", ".join(sorted(missing)))
        rows = list(reader)

    if not rows:
        raise ValidationError("El archivo de calificaciones está vacío.")

    dialects = set(config["dialects"])
    aliases = {model["alias"] for model in config["models"]}
    dimensions = set(config["dimensions"])
    item_ids = {f"I{i:03d}" for i in range(1, config["items"] + 1)}
    repetitions = set(range(1, config["repetitions"] + 1))
    seen: set[tuple[str, str, str]] = set()
    raters_by_cell: dict[tuple[str, str, str, int, str], set[str]] = {}
    responses: set[tuple[str, str, str, int]] = set()

    for line_number, row in enumerate(rows, start=2):
        response_id = row["response_id"].strip()
        item_id = row["item_id"].strip()
        dialect = row["dialect"].strip()
        model_alias = row["model_alias"].strip()
        rater_id = row["rater_id"].strip()
        dimension = row["dimension"].strip()
        try:
            replicate = int(row["replicate"])
            score = int(row["score"])
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Línea {line_number}: replicate y score deben ser enteros.") from exc

        if item_id not in item_ids:
            raise ValidationError(f"Línea {line_number}: item_id fuera del banco: {item_id}.")
        if dialect not in dialects or model_alias not in aliases or dimension not in dimensions:
            raise ValidationError(f"Línea {line_number}: dialect, model_alias o dimension desconocido.")
        if replicate not in repetitions:
            raise ValidationError(f"Línea {line_number}: replicate debe estar entre 1 y 3.")
        if not 1 <= score <= 5:
            raise ValidationError(f"Línea {line_number}: score debe estar entre 1 y 5.")
        if not all((response_id, rater_id)):
            raise ValidationError(f"Línea {line_number}: response_id y rater_id son obligatorios.")

        rating_key = (response_id, rater_id, dimension)
        if rating_key in seen:
            raise ValidationError(f"Línea {line_number}: calificación duplicada {rating_key}.")
        seen.add(rating_key)
        response_key = (item_id, dialect, model_alias, replicate)
        responses.add(response_key)
        cell_key = (*response_key, dimension)
        raters_by_cell.setdefault(cell_key, set()).add(rater_id)

    if require_complete:
        expected = {
            (f"I{i:03d}", dialect, alias, rep)
            for i in range(1, config["items"] + 1)
            for dialect in dialects
            for alias in aliases
            for rep in repetitions
        }
        missing_responses = expected - responses
        if missing_responses:
            raise ValidationError(
                f"Faltan {len(missing_responses)} combinaciones de respuesta; "
                f"ejemplo: {sorted(missing_responses)[0]}."
            )
        expected_cells = {(*response, dimension) for response in expected for dimension in dimensions}
        missing_cells = expected_cells - raters_by_cell.keys()
        under_rated = [cell for cell in expected_cells & raters_by_cell.keys()
                       if len(raters_by_cell[cell]) < minimum_raters]
        if missing_cells:
            raise ValidationError(f"Faltan {len(missing_cells)} celdas respuesta-dimensión.")
        if under_rated:
            raise ValidationError(
                f"{len(under_rated)} celdas tienen menos de {minimum_raters} evaluadores."
            )

    return {"rating_rows": len(rows), "responses": len(responses),
            "dimensions": len(dimensions), "evaluators": len({row["rater_id"] for row in rows})}

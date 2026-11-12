"""Reproducible, resumable pilot execution through the OpenAI Responses API.

The planner is offline. API calls happen only through ``run-pilot --execute``.
Pilot outputs are local run artifacts and are deliberately excluded from Git.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .validation import ValidationError, load_config, validate_config, validate_item_bank

API_URL = "https://api.openai.com/v1/responses"
DEFAULT_BANK = Path(__file__).resolve().parents[1] / "data" / "item_bank_v2.json"
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "study_config.json"


class RunnerError(RuntimeError):
    """Raised when a run cannot safely continue."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_local_api_key(api_key_env: str) -> str:
    """Read the API key from the process environment or the repository .env.

    The local file is intentionally limited to simple KEY=value lines; values
    already present in the process environment take precedence.
    """
    value = os.environ.get(api_key_env, "").strip()
    if value:
        return value

    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return ""
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("#") or "=" not in candidate:
            continue
        name, raw_value = candidate.split("=", 1)
        if name.strip() != api_key_env:
            continue
        raw_value = raw_value.strip()
        if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in "\"'":
            raw_value = raw_value[1:-1]
        return raw_value.strip()
    return ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RunnerError(f"JSONL inválido en {path}, línea {line_number}.") from exc
            if not isinstance(record, dict):
                raise RunnerError(f"Registro JSONL no es objeto en {path}, línea {line_number}.")
            records.append(record)
    return records


def import_completed_pilot_responses(
    *, full_run_dir: str | Path, pilot_run_dir: str | Path,
) -> dict[str, int]:
    """Copy matching successful pilot records into a full-study run exactly once."""
    full_dir = Path(full_run_dir).resolve()
    pilot_dir = Path(pilot_run_dir).resolve()
    full_manifest = json.loads((full_dir / "manifest.json").read_text(encoding="utf-8"))
    pilot_manifest = json.loads((pilot_dir / "manifest.json").read_text(encoding="utf-8"))
    if full_manifest.get("phase") != "main":
        raise RunnerError("El destino debe ser una corrida completa (phase=main).")
    if pilot_manifest.get("phase") != "pilot":
        raise RunnerError("El origen debe ser una corrida piloto.")
    if full_manifest.get("generation") != pilot_manifest.get("generation"):
        raise RunnerError("Los parámetros de generación difieren entre piloto y estudio completo.")

    full_schedule = _load_jsonl(full_dir / "schedule.jsonl")
    pilot_schedule = _load_jsonl(pilot_dir / "schedule.jsonl")
    full_by_key = {row["call_key"]: row for row in full_schedule}
    pilot_by_key = {row["call_key"]: row for row in pilot_schedule}
    full_records_path = full_dir / "responses.jsonl"
    existing = _load_jsonl(full_records_path)
    existing_keys = {row.get("call_key") for row in existing if row.get("status") == "completed"}
    imported_keys = {row.get("call_key") for row in existing if row.get("source_run_id") == pilot_manifest["run_id"]}
    source_records = _load_jsonl(pilot_dir / "responses.jsonl")
    to_import: list[dict[str, Any]] = []
    for record in source_records:
        key = record.get("call_key")
        if record.get("status") != "completed" or key not in full_by_key:
            continue
        if key not in pilot_by_key:
            raise RunnerError(f"La respuesta piloto no existe en su calendario: {key}.")
        if record.get("prompt_sha256") != full_by_key[key].get("prompt_sha256"):
            raise RunnerError(f"El prompt no coincide para {key}; no se importó el piloto.")
        if record.get("requested_model_id") != full_by_key[key].get("model_id"):
            raise RunnerError(f"El modelo no coincide para {key}; no se importó el piloto.")
        if key in existing_keys:
            continue
        imported = dict(record)
        imported["source_run_id"] = record.get("run_id")
        imported["source_batch"] = record.get("batch")
        imported["run_id"] = full_manifest["run_id"]
        imported["batch"] = full_by_key[key]["batch"]
        imported["reused_from_pilot"] = True
        to_import.append(imported)
        existing_keys.add(key)
    for record in to_import:
        _append_jsonl(full_records_path, record)
    full_manifest["pilot_reuse"] = {
        "source_run_id": pilot_manifest["run_id"],
        "imported_completed_calls": len(imported_keys) + len(to_import),
        "source_manifest_sha256": _sha256(pilot_dir / "manifest.json"),
        "source_responses_sha256": _sha256(pilot_dir / "responses.jsonl"),
    }
    _write_json(full_dir / "manifest.json", full_manifest)
    return {"imported": len(to_import), "already_present": len(imported_keys),
            "skipped_not_completed_or_not_in_full_schedule": sum(
                1 for record in source_records
                if record.get("status") != "completed" or record.get("call_key") not in full_by_key
            )}


def summarize_run(run_dir: str | Path) -> dict[str, Any]:
    """Return progress metadata without exposing prompt or response text."""
    output_dir = Path(run_dir).resolve()
    manifest_path = output_dir / "manifest.json"
    schedule_path = output_dir / "schedule.jsonl"
    if not manifest_path.is_file() or not schedule_path.is_file():
        raise RunnerError("Falta manifest.json o schedule.jsonl; carpeta de corrida inválida.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    schedule = _load_jsonl(schedule_path)
    records = _load_jsonl(output_dir / "responses.jsonl")

    completed = {r.get("call_key") for r in records if r.get("status") == "completed"}
    planned_keys = {call.get("call_key") for call in schedule}
    pending = planned_keys - completed
    unresolved_failures = {
        r.get("call_key") for r in records
        if r.get("status") in {"failed", "incomplete"} and r.get("call_key") not in completed
    }
    by_model: dict[str, dict[str, int]] = {}
    by_batch: dict[str, dict[str, int]] = {}
    item_calls: dict[str, int] = {}
    pair_models: dict[str, set[str]] = {}
    for call in schedule:
        key = call["call_key"]
        alias = call["model_alias"]
        batch = call["batch"]
        item = call["item_id"]
        by_model.setdefault(alias, {"planned": 0, "completed": 0, "pending": 0})
        by_batch.setdefault(batch, {"planned": 0, "completed": 0, "pending": 0})
        by_model[alias]["planned"] += 1
        by_batch[batch]["planned"] += 1
        if key in completed:
            by_model[alias]["completed"] += 1
            by_batch[batch]["completed"] += 1
            item_calls[item] = item_calls.get(item, 0) + 1
            pair_models.setdefault(call["pair_id"], set()).add(alias)
        else:
            by_model[alias]["pending"] += 1
            by_batch[batch]["pending"] += 1

    latest = max(records, key=lambda r: r.get("attempted_at_utc", ""), default=None)
    latest_public = None
    if latest:
        latest_public = {
            field: latest.get(field)
            for field in ("attempted_at_utc", "item_id", "dialect", "model_alias", "replicate", "status")
        }
    complete_item_count = sum(
        1 for item in {c["item_id"] for c in schedule}
        if item_calls.get(item, 0) == sum(1 for c in schedule if c["item_id"] == item)
    )
    return {
        "run_id": manifest.get("run_id"),
        "phase": manifest.get("phase"),
        "analysis_eligible": manifest.get("analysis_eligible"),
        "planned_calls": len(schedule),
        "completed_unique_calls": len(completed & planned_keys),
        "pending_unique_calls": len(pending),
        "failed_attempt_records": sum(1 for r in records if r.get("status") in {"failed", "incomplete"}),
        "unresolved_failed_call_keys": len(unresolved_failures),
        "completed_paired_conditions": sum(1 for aliases in pair_models.values() if len(aliases) == 2),
        "completed_items": complete_item_count,
        "by_model": by_model,
        "by_batch": by_batch,
        "latest_attempt": latest_public,
    }


def _output_text(response: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    return "".join(chunks)


def _response_cost(usage: dict[str, Any], model: dict[str, Any]) -> float:
    input_tokens = int(usage.get("input_tokens", 0))
    output_tokens = int(usage.get("output_tokens", 0))
    return (
        input_tokens * float(model["input_usd_per_million"])
        + output_tokens * float(model["output_usd_per_million"])
    ) / 1_000_000


def prepare_pilot_plan(
    *,
    run_id: str,
    run_dir: str | Path,
    model_aliases: list[str] | None = None,
    config_path: str | Path = DEFAULT_CONFIG,
    bank_path: str | Path = DEFAULT_BANK,
    daily_request_limit: int | None = None,
    include_all_items: bool = False,
) -> dict[str, Any]:
    """Create a deterministic, offline plan with complete paired item blocks.

    Each item contributes 12 calls per model (4 dialects x 3 replicates).
    Items are kept intact and assigned to UTC-day batches that remain under
    the supplied per-model daily request limit.
    """
    if not run_id.strip() or any(ch in run_id for ch in "/\\"):
        raise RunnerError("run_id debe ser un identificador simple, sin rutas.")
    config_file = Path(config_path).resolve()
    bank_file = Path(bank_path).resolve()
    output_dir = Path(run_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise RunnerError(f"La carpeta de corrida ya existe y contiene archivos: {output_dir}")

    config = load_config(config_file)
    validate_config(config)
    validate_item_bank(bank_file, config)
    if daily_request_limit is None:
        daily_request_limit = int(config.get("execution", {}).get(
            "local_requests_per_rolling_24h_per_model", 100
        ))
    if daily_request_limit < 12:
        raise RunnerError("El límite diario debe permitir al menos un ítem completo por modelo (12 llamadas).")
    items = json.loads(bank_file.read_text(encoding="utf-8-sig"))
    items_by_id = {item["item_id"]: item for item in items}
    pilot_ids = (list(items_by_id) if include_all_items
                 else list(config.get("pilot_items", [])))
    if not pilot_ids or any(item_id not in items_by_id for item_id in pilot_ids):
        raise RunnerError("pilot_items debe apuntar a IDs existentes en el banco.")

    models = {model["alias"]: model for model in config.get("models", [])}
    selected_aliases = model_aliases or list(models)
    if len(selected_aliases) != len(set(selected_aliases)):
        raise RunnerError("No repitas alias de modelo en el plan.")
    missing_aliases = [alias for alias in selected_aliases if alias not in models]
    if not selected_aliases or missing_aliases:
        raise RunnerError("Alias de modelo desconocido o lista vacía: " + ", ".join(missing_aliases))

    calls_per_item_model = len(config["dialects"]) * int(config["repetitions"])
    items_per_batch = max(1, daily_request_limit // calls_per_item_model)
    seed = int(config["randomization_seed"])
    rng = random.Random(seed)
    scheduled: list[dict[str, Any]] = []
    sequence = 0

    # Keep a complete item (all four dialects and three replicates) together.
    for start in range(0, len(pilot_ids), items_per_batch):
        batch_number = start // items_per_batch + 1
        batch_ids = pilot_ids[start:start + items_per_batch]
        rng.shuffle(batch_ids)
        for item_id in batch_ids:
            item = items_by_id[item_id]
            conditions = [(dialect, replicate)
                          for dialect in config["dialects"]
                          for replicate in range(1, int(config["repetitions"]) + 1)]
            rng.shuffle(conditions)
            for dialect, replicate in conditions:
                pair_id = f"{item_id}:{dialect}:r{replicate}"
                aliases = list(selected_aliases)
                # Counterbalance model order within each paired condition.
                if len(aliases) == 2 and rng.randrange(2):
                    aliases.reverse()
                for alias in aliases:
                    sequence += 1
                    prompt = item[f"prompt_{dialect}"]
                    scheduled.append({
                        "sequence": sequence,
                        "batch": f"day{batch_number}",
                        "run_id": run_id,
                        "call_key": f"{item_id}:{dialect}:{alias}:r{replicate}",
                        "pair_id": pair_id,
                        "item_id": item_id,
                        "dialect": dialect,
                        "model_alias": alias,
                        "model_id": models[alias]["model_id"],
                        "replicate": replicate,
                        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                        "prompt": prompt,
                    })

    per_batch: dict[str, dict[str, int]] = {}
    for call in scheduled:
        counts = per_batch.setdefault(call["batch"], {})
        counts[call["model_alias"]] = counts.get(call["model_alias"], 0) + 1
    over_limit = [(batch, alias, count) for batch, models_count in per_batch.items()
                  for alias, count in models_count.items() if count > daily_request_limit]
    if over_limit:
        raise RunnerError(f"El plan supera el límite diario por modelo: {over_limit}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "inputs").mkdir()
    (output_dir / "inputs" / "study_config.json").write_bytes(config_file.read_bytes())
    (output_dir / "inputs" / "item_bank.json").write_bytes(bank_file.read_bytes())
    schedule_path = output_dir / "schedule.jsonl"
    with schedule_path.open("w", encoding="utf-8", newline="\n") as stream:
        for call in scheduled:
            stream.write(json.dumps(call, ensure_ascii=False, sort_keys=True) + "\n")

    model_snapshot = [{
        "alias": alias,
        "requested_model_id": models[alias]["model_id"],
        "snapshot_policy": models[alias]["snapshot"],
        "input_usd_per_million": models[alias]["input_usd_per_million"],
        "output_usd_per_million": models[alias]["output_usd_per_million"],
    } for alias in selected_aliases]
    local_rolling_limit = int(config.get("execution", {}).get(
        "local_requests_per_rolling_24h_per_model", 100
    ))
    manifest = {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at_utc": _utc_now(),
        "phase": "main" if include_all_items else "pilot",
        "analysis_eligible": False,
        "schedule_policy": "complete item blocks; paired model calls; seeded order",
        "randomization_seed": seed,
        "items": pilot_ids,
        "dialects": config["dialects"],
        "repetitions": config["repetitions"],
        "models": model_snapshot,
        "local_request_limit_per_model_rolling_24h": local_rolling_limit,
        "max_requests_per_model_per_batch": daily_request_limit,
        "requests_per_minute": config.get("execution", {}).get("requests_per_minute", {}),
        "generation": {
            "system_instruction": config["generation"]["system_instruction"],
            "reasoning_effort": config["generation"]["native_effort"],
            "max_output_tokens": config["generation"]["max_output_tokens"],
            "tools_enabled": config["generation"]["tools_enabled"],
            "store": config["generation"].get("store", False),
            "temperature": "omitted",
            "top_p": "omitted",
            "single_turn": True,
        },
        "input_hashes": {
            "config_sha256": _sha256(config_file),
            "bank_sha256": _sha256(bank_file),
            "schedule_sha256": _sha256(schedule_path),
        },
        "calls_per_batch_per_model": per_batch,
        "total_calls": len(scheduled),
        "inputs_are_snapshotted": True,
        "notes": [
            "No API request was made while creating this plan.",
            ("All 60 items are scheduled for the 1,440-response study; import completed pilot records before execution. Analysis remains gated by the documented approvals."
             if include_all_items else
             "Pilot outputs are exploratory and excluded from the main study unless the protocol explicitly incorporates them."),
            "The account quota can change; re-check Limits before each daily batch.",
        ],
    }
    _write_json(output_dir / "manifest.json", manifest)
    return manifest


def _post_response(payload: dict[str, Any], api_key: str, timeout: int = 120) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            error = detail.get("error", {})
            message = error.get("message", "API request failed")
            code = error.get("code")
        except (UnicodeDecodeError, json.JSONDecodeError):
            message, code = "API request failed; response body was not JSON", None
        raise RunnerError(f"OpenAI API HTTP {exc.code} ({code}): {message}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RunnerError(f"No se pudo completar la solicitud API: {exc}") from exc
    if not isinstance(data, dict):
        raise RunnerError("La API devolvió una respuesta JSON inesperada.")
    return data


def execute_pilot_batch(
    *,
    run_dir: str | Path,
    batch: str,
    api_key_env: str = "OPENAI_API_KEY",
    retry_failed: bool = False,
    model_aliases: list[str] | None = None,
    max_new_requests_per_model: int | None = None,
) -> dict[str, int]:
    """Execute one preplanned batch; successful call keys are never duplicated.

    Model filtering supports deliberate recovery when one model reaches a rate
    limit before its paired model. Pair IDs remain unchanged so later calls can
    complete the comparison.
    """
    output_dir = Path(run_dir).resolve()
    manifest_path = output_dir / "manifest.json"
    schedule_path = output_dir / "schedule.jsonl"
    responses_path = output_dir / "responses.jsonl"
    stop_file = output_dir / "STOP_AFTER_CURRENT"
    if not manifest_path.is_file() or not schedule_path.is_file():
        raise RunnerError("Falta manifest.json o schedule.jsonl; crea primero el plan.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") not in {"pilot", "main"}:
        raise RunnerError("Fase de corrida no reconocida por este ejecutor.")
    if batch not in manifest.get("calls_per_batch_per_model", {}):
        raise RunnerError(f"Lote desconocido: {batch}.")
    if max_new_requests_per_model is not None and max_new_requests_per_model < 1:
        raise RunnerError("max_new_requests_per_model debe ser al menos 1.")

    api_key = _load_local_api_key(api_key_env)
    if not api_key:
        raise RunnerError(f"Falta la variable de entorno {api_key_env}; no se realizó ninguna llamada.")
    records = _load_jsonl(responses_path)
    completed = {record.get("call_key") for record in records if record.get("status") == "completed"}
    models = {model["alias"]: model for model in manifest["models"]}
    selected_aliases = model_aliases or list(models)
    unknown_aliases = set(selected_aliases) - set(models)
    if not selected_aliases or unknown_aliases:
        raise RunnerError("Alias de modelo desconocido o lista vacía: " + ", ".join(sorted(unknown_aliases)))
    selected_models = {alias: models[alias] for alias in selected_aliases}
    planned = [call for call in _load_jsonl(schedule_path)
               if call["batch"] == batch and call["model_alias"] in selected_models]
    if not planned:
        raise RunnerError("No hay llamadas pendientes para el lote y los modelos seleccionados.")
    rpm = manifest.get("requests_per_minute", {})
    # Backward compatibility: older plans called this a daily API limit even
    # though it was only a client-side rolling-window safeguard.
    per_model_limit = int(manifest.get(
        "local_request_limit_per_model_rolling_24h",
        manifest.get("per_model_daily_request_limit", 100),
    ))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    attempted_window: dict[str, int] = {}
    for record in records:
        attempted_at = record.get("attempted_at_utc")
        try:
            parsed_time = datetime.fromisoformat(attempted_at) if attempted_at else None
        except ValueError:
            parsed_time = None
        if parsed_time is not None and parsed_time >= cutoff:
            alias = record.get("model_alias")
            attempted_window[alias] = attempted_window.get(alias, 0) + 1

    failed_keys = {record.get("call_key") for record in records
                   if record.get("status") in {"failed", "incomplete"}
                   and record.get("model_alias") in selected_models}
    unresolved_failures = failed_keys - completed
    if unresolved_failures and not retry_failed:
        example = sorted(unresolved_failures)[0]
        raise RunnerError(
            f"Hay un intento fallido/incompleto para {example}. Revísalo antes de repetir; "
            "si aceptas el posible cargo duplicado, usa --retry-failed."
        )

    # Admit only complete item blocks under the remaining rolling 24-hour quota.
    item_order = list(dict.fromkeys(call["item_id"] for call in planned))
    permitted_items: set[str] = set()
    remaining = {alias: max(0, per_model_limit - attempted_window.get(alias, 0))
                 for alias in selected_models}
    invocation_remaining = {alias: (max_new_requests_per_model
                                     if max_new_requests_per_model is not None
                                     else len(planned))
                            for alias in selected_models}
    for item_id in item_order:
        item_calls = [call for call in planned if call["item_id"] == item_id]
        needed = {alias: sum(1 for call in item_calls
                             if call["model_alias"] == alias and call["call_key"] not in completed)
                  for alias in selected_models}
        if any(needed[alias] > min(remaining.get(alias, 0),
                                   invocation_remaining.get(alias, 0))
               for alias in selected_models):
            break
        permitted_items.add(item_id)
        for alias in selected_models:
            remaining[alias] -= needed[alias]
            invocation_remaining[alias] -= needed[alias]

    last_request_at: dict[str, float] = {}
    result_counts = {"completed": 0, "skipped": 0, "failed": 0, "deferred": 0}

    for index, call in enumerate(planned):
        if stop_file.exists():
            result_counts["deferred"] += sum(
                1 for pending_call in planned[index:]
                if pending_call["call_key"] not in completed
            )
            break
        if call["call_key"] in completed:
            result_counts["skipped"] += 1
            continue
        if call["item_id"] not in permitted_items:
            result_counts["deferred"] += 1
            continue
        alias = call["model_alias"]
        model = selected_models[alias]
        if attempted_window.get(alias, 0) >= per_model_limit:
            raise RunnerError(
                f"Se alcanzó el tope local de {per_model_limit} intentos en 24 horas para {alias}."
            )
        try:
            rpm_limit = int(rpm.get(alias, 1))
        except (TypeError, ValueError):
            rpm_limit = 1
        if rpm_limit < 1:
            raise RunnerError(f"requests_per_minute inválido para {alias}.")
        interval = 60.0 / rpm_limit
        previous = last_request_at.get(alias)
        if previous is not None:
            remaining = interval - (time.monotonic() - previous)
            if remaining > 0:
                time.sleep(remaining)
        if stop_file.exists():
            result_counts["deferred"] += sum(
                1 for pending_call in planned[index:]
                if pending_call["call_key"] not in completed
            )
            break

        attempted_at = _utc_now()
        started = time.monotonic()
        payload = {
            "model": call["model_id"],
            "input": [
                {"role": "system", "content": manifest["generation"]["system_instruction"]},
                {"role": "user", "content": call["prompt"]},
            ],
            "reasoning": {"effort": manifest["generation"]["reasoning_effort"][alias]},
            "max_output_tokens": int(manifest["generation"]["max_output_tokens"]),
            "store": bool(manifest["generation"]["store"]),
        }
        if stop_file.exists():
            result_counts["deferred"] += sum(
                1 for pending_call in planned[index:]
                if pending_call["call_key"] not in completed
            )
            break
        last_request_at[alias] = time.monotonic()
        attempted_window[alias] = attempted_window.get(alias, 0) + 1
        try:
            response = _post_response(payload, api_key)
        except RunnerError as exc:
            record = {
                "run_id": manifest["run_id"],
                "call_key": call["call_key"],
                "pair_id": call["pair_id"],
                "item_id": call["item_id"],
                "dialect": call["dialect"],
                "model_alias": alias,
                "requested_model_id": call["model_id"],
                "replicate": call["replicate"],
                "batch": batch,
                "attempted_at_utc": attempted_at,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "status": "failed",
                "error": str(exc),
            }
            _append_jsonl(responses_path, record)
            result_counts["failed"] += 1
            raise

        usage = response.get("usage") or {}
        api_status = response.get("status")
        record = {
            "run_id": manifest["run_id"],
            "call_key": call["call_key"],
            "pair_id": call["pair_id"],
            "item_id": call["item_id"],
            "dialect": call["dialect"],
            "model_alias": alias,
            "requested_model_id": call["model_id"],
            "returned_model_id": response.get("model"),
            "replicate": call["replicate"],
            "batch": batch,
            "response_id": response.get("id"),
            "attempted_at_utc": attempted_at,
            "completed_at_utc": _utc_now(),
            "latency_ms": round((time.monotonic() - started) * 1000),
            "status": "completed" if api_status == "completed" else "incomplete",
            "api_status": api_status,
            "output_text": _output_text(response),
            "usage": usage,
            "estimated_cost_usd": round(_response_cost(usage, model), 8),
            "prompt_sha256": call["prompt_sha256"],
        }
        _append_jsonl(responses_path, record)
        if api_status != "completed":
            result_counts["failed"] += 1
            raise RunnerError(
                f"La API terminó {call['call_key']} con estado {api_status!r}; "
                "revisa el registro antes de decidir si repetirlo."
            )
        completed.add(call["call_key"])
        result_counts["completed"] += 1

    return result_counts

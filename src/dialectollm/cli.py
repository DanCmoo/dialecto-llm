"""Command-line entry point for DIALECTO-LLM data-contract validation."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .runner import (RunnerError, execute_pilot_batch, import_completed_pilot_responses,
                     prepare_pilot_plan, summarize_run)
from .validation import (
    ValidationError, load_config, validate_config, validate_item_bank,
    validate_language_review_template, validate_ratings_csv,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "study_config.json"
DEFAULT_BANK_V2 = Path(__file__).resolve().parents[1] / "data" / "item_bank_v2.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dialectollm", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    config_cmd = commands.add_parser("validate-config", help="validar invariantes del diseño")
    config_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    config_cmd.add_argument("--ready", action="store_true",
                            help="exigir identificadores y snapshots de ambos modelos")

    ratings_cmd = commands.add_parser("validate-ratings", help="validar una matriz CSV de calificaciones")
    ratings_cmd.add_argument("csv_file", type=Path)
    ratings_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    ratings_cmd.add_argument("--allow-incomplete", action="store_true",
                             help="omitir cobertura total (útil para revisión de borradores)")

    bank_cmd = commands.add_parser("validate-item-bank", help="validar el banco pareado de 60 ítems")
    bank_cmd.add_argument("--bank", type=Path,
                          default=Path(__file__).resolve().parents[1] / "data" / "item_bank_v1.json")
    bank_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG)

    review_cmd = commands.add_parser("validate-language-review", help="revisar la plantilla de naturalidad/equivalencia")
    review_cmd.add_argument("csv_file", type=Path)
    review_cmd.add_argument("--require-approved", action="store_true",
                            help="exigir dos revisiones aprobatorias completas por variante")

    plan_cmd = commands.add_parser(
        "plan-pilot", help="crear un plan offline y reproducible del piloto"
    )
    plan_cmd.add_argument("--run-id", required=True, help="identificador estable de corrida")
    plan_cmd.add_argument("--run-dir", type=Path, required=True,
                          help="carpeta local para manifiesto, entradas congeladas y resultados")
    plan_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    plan_cmd.add_argument("--bank", type=Path, default=DEFAULT_BANK_V2)
    plan_cmd.add_argument("--model-alias", action="append", dest="model_aliases",
                          help="alias a incluir; se puede repetir (por defecto, ambos modelos)")
    plan_cmd.add_argument("--local-rolling-24h-limit", "--daily-request-limit",
                          dest="daily_request_limit", type=int,
                          help="salvaguarda local de intentos por modelo en 24 h; no es un límite API")

    full_plan_cmd = commands.add_parser(
        "plan-full", help="planificar los 60 ítems del experimento (1,440 llamadas totales)"
    )
    full_plan_cmd.add_argument("--run-id", required=True)
    full_plan_cmd.add_argument("--run-dir", type=Path, required=True)
    full_plan_cmd.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    full_plan_cmd.add_argument("--bank", type=Path, default=DEFAULT_BANK_V2)
    full_plan_cmd.add_argument("--model-alias", action="append", dest="model_aliases")
    full_plan_cmd.add_argument("--daily-request-limit", type=int, default=48,
                               help="llamadas por modelo en cada lote; 48 deja margen bajo RPD=50")

    import_cmd = commands.add_parser(
        "import-pilot", help="integrar respuestas completadas del piloto en la corrida completa"
    )
    import_cmd.add_argument("full_run_dir", type=Path)
    import_cmd.add_argument("pilot_run_dir", type=Path)

    run_cmd = commands.add_parser(
        "run-pilot", help="ejecutar/reanudar un lote preplaneado (genera costo API)"
    )
    run_cmd.add_argument("run_dir", type=Path)
    run_cmd.add_argument("--batch", required=True, help="lote UTC, por ejemplo day1")
    run_cmd.add_argument("--model-alias", action="append", dest="model_aliases",
                         help="restringir ejecución a uno o más alias; puede dejar pares pendientes")
    run_cmd.add_argument("--api-key-env", default="OPENAI_API_KEY",
                         help="nombre de variable local que contiene la clave API")
    run_cmd.add_argument("--retry-failed", action="store_true",
                         help="repetir llamadas fallidas tras revisar si pudieron generar cargo")
    run_cmd.add_argument("--max-new-requests-per-model", type=int,
                         help="tope de llamadas nuevas por modelo en esta invocación")
    run_cmd.add_argument("--execute", action="store_true",
                         help="confirmar explícitamente el envío de llamadas pagadas")

    status_cmd = commands.add_parser(
        "run-status", help="ver progreso de una corrida sin imprimir respuestas"
    )
    status_cmd.add_argument("run_dir", type=Path)
    status_cmd.add_argument("--watch", action="store_true", help="actualizar periódicamente")
    status_cmd.add_argument("--interval", type=float, default=5.0,
                            help="segundos entre actualizaciones (por defecto: 5)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-language-review":
            print(json.dumps(validate_language_review_template(
                args.csv_file, require_complete=args.require_approved
            ), ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-pilot":
            manifest = prepare_pilot_plan(
                run_id=args.run_id,
                run_dir=args.run_dir,
                model_aliases=args.model_aliases,
                config_path=args.config,
                bank_path=args.bank,
                daily_request_limit=args.daily_request_limit,
            )
            print(json.dumps({
                "run_id": manifest["run_id"],
                "run_dir": str(args.run_dir.resolve()),
                "total_calls": manifest["total_calls"],
                "calls_per_batch_per_model": manifest["calls_per_batch_per_model"],
                "analysis_eligible": manifest["analysis_eligible"],
                "api_calls_made": 0,
            }, ensure_ascii=False, indent=2))
            return 0
        if args.command == "plan-full":
            manifest = prepare_pilot_plan(
                run_id=args.run_id, run_dir=args.run_dir,
                model_aliases=args.model_aliases, config_path=args.config,
                bank_path=args.bank, daily_request_limit=args.daily_request_limit,
                include_all_items=True,
            )
            print(json.dumps({
                "run_id": manifest["run_id"], "run_dir": str(args.run_dir.resolve()),
                "total_calls": manifest["total_calls"],
                "calls_per_batch_per_model": manifest["calls_per_batch_per_model"],
                "analysis_eligible": manifest["analysis_eligible"],
                "api_calls_made": 0,
            }, ensure_ascii=False, indent=2))
            return 0
        if args.command == "import-pilot":
            result = import_completed_pilot_responses(
                full_run_dir=args.full_run_dir, pilot_run_dir=args.pilot_run_dir,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "run-pilot":
            if not args.execute:
                raise RunnerError("Sin --execute no se envían llamadas ni se genera consumo API.")
            summary = execute_pilot_batch(
                run_dir=args.run_dir,
                batch=args.batch,
                api_key_env=args.api_key_env,
                retry_failed=args.retry_failed,
                model_aliases=args.model_aliases,
                max_new_requests_per_model=args.max_new_requests_per_model,
            )
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        if args.command == "run-status":
            if args.interval <= 0:
                raise RunnerError("--interval debe ser mayor que cero.")
            while True:
                summary = summarize_run(args.run_dir)
                if args.watch:
                    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    models = " ".join(
                        f"{alias}={counts['completed']}/{counts['planned']}"
                        for alias, counts in sorted(summary["by_model"].items())
                    )
                    latest = summary["latest_attempt"] or {}
                    last = ":".join(str(latest.get(field) or "-") for field in
                                     ("item_id", "dialect", "model_alias", "replicate", "status"))
                    print(
                        f"{stamp} run={summary['run_id']} "
                        f"calls={summary['completed_unique_calls']}/{summary['planned_calls']} "
                        f"pending={summary['pending_unique_calls']} "
                        f"paired={summary['completed_paired_conditions']} "
                        f"unresolved={summary['unresolved_failed_call_keys']} "
                        f"models=[{models}] last={last}",
                        flush=True,
                    )
                    time.sleep(args.interval)
                else:
                    print(json.dumps(summary, ensure_ascii=False, indent=2))
                    return 0
        config = load_config(args.config)
        if args.command == "validate-config":
            warnings = validate_config(config, require_models=args.ready)
            print("Configuración estructural válida.")
            for warning in warnings:
                print("PENDIENTE:", warning)
            if config.get("status") == "design_only":
                print("Estado: design_only; esto no autoriza ni ejecuta llamadas a modelos.")
            if args.ready:
                print("Diseño listo para integrarse con un ejecutor de consultas.")
            return 0

        if args.command == "validate-item-bank":
            print(json.dumps(validate_item_bank(args.bank, config), ensure_ascii=False, indent=2))
            return 0

        summary = validate_ratings_csv(
            args.csv_file, config, require_complete=not args.allow_incomplete
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ValidationError, RunnerError) as exc:
        print(f"Error de validación: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

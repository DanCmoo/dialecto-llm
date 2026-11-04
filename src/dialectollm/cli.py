"""Command-line entry point for DIALECTO-LLM data-contract validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .validation import (
    ValidationError, load_config, validate_config, validate_item_bank,
    validate_language_review_template, validate_ratings_csv,
)

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "study_config.json"


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-language-review":
            print(json.dumps(validate_language_review_template(
                args.csv_file, require_complete=args.require_approved
            ), ensure_ascii=False, indent=2))
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
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Error de validación: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

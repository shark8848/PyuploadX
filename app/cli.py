"""Command line interface: python -m upload_service <command>."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.config.loader import load_settings
from app.config.models import Settings
from app.config.validation import validate_settings
from app.db.session import build_engine, build_session_factory
from app.services.reconcile_service import ReconcileService
from app.storage.factory import build_storage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="upload-service")
    parser.add_argument("--config", help="path to YAML config file")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config", help="configuration utilities")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    config_sub.add_parser("validate", help="validate configuration")
    show = config_sub.add_parser("show", help="show effective configuration")
    show.add_argument("--redact-secrets", action="store_true")

    reconcile = sub.add_parser("reconcile", help="reconcile state with storage")
    reconcile.add_argument("kind", choices=["upload", "file", "directory"])
    reconcile.add_argument("id")
    reconcile.add_argument("--dry-run", action="store_true")
    return parser


def _redact(settings: Settings) -> Settings:
    import copy

    redacted = copy.deepcopy(settings)
    redacted.database.url = redacted.database.url or ""
    redacted.redis.url = redacted.redis.url or ""
    redacted.storage.s3.access_key = "***"
    redacted.storage.s3.secret_key = "***"
    return redacted


def _config_command(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    if args.config_command == "validate":
        result = validate_settings(settings)
        if result.ok:
            print("configuration is valid")
            return 0
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    if args.config_command == "show":
        shown = _redact(settings) if args.redact_secrets else settings
        print(json.dumps(shown.model_dump(), indent=2, default=str))
        return 0
    return 1


def _reconcile_command(args: argparse.Namespace) -> int:
    settings = load_settings(args.config)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    storage = build_storage(settings)

    async def run() -> int:
        import uuid

        async with session_factory() as session:
            service = ReconcileService(storage)
            if args.kind == "upload":
                report = await service.reconcile_upload(session, uuid.UUID(args.id))
                print(json.dumps(report.__dict__, indent=2, default=str))
                return 0 if report.consistent else 1
            print(f"reconcile {args.kind} {args.id}: not implemented yet", file=sys.stderr)
            return 1

    return asyncio.run(run())


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "config":
        return _config_command(args)
    if args.command == "reconcile":
        return _reconcile_command(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

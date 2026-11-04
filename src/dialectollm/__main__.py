"""Allow ``python -m dialectollm`` after installing the local package."""

from .cli import main

raise SystemExit(main())

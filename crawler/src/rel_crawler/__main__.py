"""Allow ``python -m rel_crawler`` to invoke the command-line client."""

from .cli import main

raise SystemExit(main())

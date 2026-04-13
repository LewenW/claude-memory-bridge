"""Create realistic demo project memories in ~/.claude/projects/.

Run once: python scripts/setup_demo.py
Clean up: python scripts/setup_demo.py --clean
"""

import sys
import shutil
from pathlib import Path

CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

DEMO_PROJECTS = {
    "-Users-demo-projects-web-frontend": {
        "MEMORY.md": "\n".join([
            "- [Package Manager](package-manager.md) — Team uses pnpm",
            "- [React Patterns](react-patterns.md) — Component conventions",
            "- [Code Review](code-review.md) — PR review process",
            "- [Error Handling](error-handling.md) — Frontend error strategy",
        ]),
        "package-manager.md": """---
name: Package Manager
description: Team uses pnpm exclusively
type: feedback
tags: pnpm, npm, ci
---

Always use pnpm, never npm or yarn.
Run `pnpm install --frozen-lockfile` in CI.
Use `pnpm dlx` instead of `npx` for one-off commands.
""",
        "react-patterns.md": """---
name: React Patterns
description: Component conventions for the frontend
type: feedback
tags: react, components, patterns
---

Use functional components only, no class components.
Colocate styles with components using CSS modules.
Prefer composition over prop drilling — use React Context for shared state.
Name event handlers with `handle` prefix: handleClick, handleSubmit.
Extract custom hooks when logic is reused across 2+ components.
""",
        "code-review.md": """---
name: Code Review
description: PR review process and conventions
type: feedback
tags: pr, review, process
---

Every PR needs at least one approval before merge.
Use conventional commits: feat:, fix:, refactor:, docs:.
Keep PRs under 400 lines when possible.
Add screenshots for UI changes.
""",
        "error-handling.md": """---
name: Error Handling
description: Frontend error strategy
type: feedback
tags: errors, sentry, monitoring
---

Use React Error Boundaries for component-level failures.
Report errors to Sentry with user context attached.
Show user-friendly error messages, log technical details.
Never swallow errors silently — at minimum log to console in dev.
""",
    },
    "-Users-demo-projects-api-backend": {
        "MEMORY.md": "\n".join([
            "- [Package Manager](package-manager.md) — Also uses pnpm",
            "- [API Design](api-design.md) — REST API conventions",
            "- [Database](database.md) — PostgreSQL patterns",
            "- [Code Review](code-review.md) — Same PR process as frontend",
        ]),
        "package-manager.md": """---
name: Package Manager
description: Backend also uses pnpm for tooling
type: feedback
tags: pnpm, npm
---

Use pnpm for all JavaScript tooling in the backend repo.
Run pnpm install --frozen-lockfile in CI pipelines.
Never use npm or yarn directly.
""",
        "api-design.md": """---
name: API Design
description: REST API conventions
type: feedback
tags: api, rest, http
---

Use kebab-case for URL paths: /user-profiles not /userProfiles.
Use camelCase for JSON request and response bodies.
All list endpoints must support pagination with cursor-based paging.
Return proper HTTP status codes: 201 for creation, 204 for deletion.
Version APIs in the URL path: /v1/users, /v2/users.
""",
        "database.md": """---
name: Database
description: PostgreSQL patterns and conventions
type: project
tags: postgres, sql, migrations
---

Use PostgreSQL for all persistent storage.
Write migrations with Prisma. Never modify the database schema manually.
Use UUIDs for primary keys, not auto-increment integers.
Add indexes for any column used in WHERE or JOIN clauses.
Use database transactions for multi-step operations.
""",
        "code-review.md": """---
name: Code Review
description: Same PR process as the frontend team
type: feedback
tags: pr, review, process
---

Every PR needs at least one approval before merge.
Use conventional commits: feat:, fix:, refactor:, docs:.
Keep PRs under 400 lines when possible.
Add API documentation for new endpoints.
""",
    },
    "-Users-demo-projects-mobile-app": {
        "MEMORY.md": "\n".join([
            "- [Tech Stack](tech-stack.md) — React Native setup",
            "- [Navigation](navigation.md) — App navigation patterns",
        ]),
        "tech-stack.md": """---
name: Tech Stack
description: React Native mobile app setup
type: project
tags: react-native, mobile, expo
---

Mobile app built with React Native + Expo (SDK 51).
State management with Zustand (same pattern as web dashboard).
Use React Navigation v6 for routing.
Target iOS 16+ and Android 13+.
""",
        "navigation.md": """---
name: Navigation
description: App navigation patterns
type: project
tags: navigation, routing, screens
---

Use stack navigation for auth flow, tab navigation for main app.
Deep linking configured for all top-level screens.
Screen names follow PascalCase: HomeScreen, ProfileScreen.
Navigation params typed with TypeScript generics.
""",
    },
}


def setup():
    created = []
    for project_id, files in DEMO_PROJECTS.items():
        mem_dir = CLAUDE_PROJECTS / project_id / "memory"
        mem_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (mem_dir / filename).write_text(content.strip() + "\n", encoding="utf-8")
        name = project_id.split("-")[-1]
        created.append(f"  {name}: {len(files) - 1} memories")

    print("Demo projects created:\n" + "\n".join(created))
    print(f"\nTotal: {sum(len(f) - 1 for f in DEMO_PROJECTS.values())} memories across {len(DEMO_PROJECTS)} projects")
    print("\nDuplicates planted:")
    print("  - 'Package Manager' in web-frontend AND api-backend (near-identical)")
    print("  - 'Code Review' in web-frontend AND api-backend (slightly different)")


def clean():
    removed = 0
    for project_id in DEMO_PROJECTS:
        project_dir = CLAUDE_PROJECTS / project_id
        if project_dir.exists():
            shutil.rmtree(project_dir)
            removed += 1
    print(f"Removed {removed} demo projects.")


if __name__ == "__main__":
    if "--clean" in sys.argv:
        clean()
    else:
        setup()

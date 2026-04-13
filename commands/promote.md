---
name: promote
description: Promote a project memory to a shared namespace
---

Help the user promote memories from the current project to a shared namespace:

1. If the user specified content, use `promote_memory` directly
2. If not, use `search_memories` with scope="project" to show current project's memories
3. Ask which memory to promote and to which namespace
4. If no namespaces exist, offer to create one first with `manage_namespaces`
5. Execute the promotion and confirm the result

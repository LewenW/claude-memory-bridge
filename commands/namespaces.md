---
name: namespaces
description: View and manage shared memory namespaces
---

Use `manage_namespaces` to help the user with namespace operations:

- No args: list all namespaces with their subscribers and memory counts
- If user wants to create: ask for name and description, then create
- If user wants to subscribe a project: show available namespaces and projects, then subscribe
- If user wants to unsubscribe or delete: confirm before proceeding

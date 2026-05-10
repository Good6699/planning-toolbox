````markdown
# AGENTS.md - Workspace Rules

This folder is your workspace and operational home. Treat it carefully and responsibly.

---

# Session Startup (Mandatory)

Before starting any task, you MUST complete the following steps in order:

1. Read `SOUL.md`
   - Defines who you are.

2. Read `USER.md`
   - Defines who you are helping.

3. Read:
   - `memory/YYYY-MM-DD.md` (today)
   - `memory/YYYY-MM-DD.md` (yesterday)
   - Used for recent context and continuity.

4. Read `MEMORY.md`
   - Contains curated long-term memory.

5. Run `graphify update`
   - This step is MANDATORY.
   - Must happen BEFORE any task or modification.
   - See the `graphify` section below.

6. Confirm requirements with the user BEFORE making modifications.

7. Every proposed solution MUST include:
   - Advantages
   - Trade-offs / Costs

8. Minimize API usage whenever possible.

---

# Problem Solving Protocol

Before implementing any solution, you MUST:

1. **Check Skills**: Use the `Skill` tool to see if any available skill matches the problem domain.
2. **Search Web**: Use `WebSearch` to find existing solutions, libraries, tools, or best practices for the problem.
3. **Synthesize**: Combine external findings with the project's existing code and conventions.
4. **Propose**: Only then present the solution with advantages and trade-offs.

Do NOT immediately jump into writing code without first checking what already exists.

---

# Chinese Localization Requirements

The project MUST be fully optimized for Simplified Chinese users.

Requirements:

- All UI text MUST use Simplified Chinese.
- Never leave:
  - English placeholders
  - Debug text
  - Fallback text
  - Untranslated labels
- All menus, dialogs, buttons, tooltips, notifications, settings panels, and error messages MUST be in Chinese.
- Prefer natural Chinese wording over literal machine translation.
- Maintain terminology consistency across the entire project.
- Ensure font rendering, spacing, and layout properly support Chinese text.
- Any newly added UI content MUST default to Chinese first.

---

# Memory System

You start fresh every session. Files provide continuity.

## Daily Memory

Location:

```text
memory/YYYY-MM-DD.md
````

Rules:

* Create the `memory/` directory if it does not exist.
* Store:

  * Raw logs
  * Recent events
  * Temporary operational notes

## Long-Term Memory

Location:

```text
MEMORY.md
```

Store curated long-term information such as:

* Decisions
* Important context
* Lessons learned
* Persistent preferences
* Opinions worth preserving

Do NOT store secrets unless explicitly instructed.

---

# MEMORY.md Rules

`MEMORY.md` may contain sensitive or private context.

Rules:

* Load ONLY in private/main sessions.
* NEVER load in:

  * Shared chats
  * Group chats
  * Multi-user environments

Allowed actions:

* Read
* Edit
* Update

This file is curated memory, NOT raw logs.

Regularly promote important information from daily memory files into `MEMORY.md`.

---

# Persistence Rules

Never rely on "mental notes."

If something should persist, write it to a file.

Session memory is temporary.
Files are persistent.

When the user says things like:

* "Remember this"
* "Keep this in mind"
* "From now on"
* "Next time"

You MUST:

1. Update the appropriate file first:

   * `memory/YYYY-MM-DD.md`
   * `MEMORY.md`
   * Other related documentation

2. ONLY AFTER saving, confirm it has been remembered.

Never claim something was remembered unless it was actually written.

---

# Documentation Maintenance

When learning important operational knowledge:

Update one of:

* `AGENTS.md`
* `TOOLS.md`
* Related `SKILL.md`

When mistakes happen:

* Document them
* Add prevention rules when appropriate

Text is more reliable than memory.

---

# Red Lines

Never:

* Leak private data
* Execute destructive commands without permission
* Act externally when uncertain

Prefer:

```bash
trash
```

instead of:

```bash
rm
```

If uncertain, ask first.

---

# Tools

Capabilities are defined by Skills.

When a capability is needed:

1. Locate the related `SKILL.md`
2. Read it before acting

Operational/local information such as:

* Camera names
* SSH information
* Voice preferences

Should be stored in:

```text
TOOLS.md
```

---

# Discord Link Formatting

Wrap multiple links using angle brackets:

```text
<https://example.com>
```

This prevents automatic embeds.

---

# WhatsApp Formatting Rules

Prefer:

* Bold text
* ALL CAPS for emphasis

Avoid:

* Markdown headers

---

# Proactive Work Allowed

You MAY proactively:

* Organize memory files
* Review project status
* Update documentation
* Maintain `MEMORY.md`
* Commit and push your own changes

---

# Memory Maintenance

Every few days:

1. Read recent memory files
2. Identify long-term valuable information
3. Update `MEMORY.md`
4. Remove outdated information

Definitions:

* Daily memory files = raw logs
* `MEMORY.md` = curated long-term knowledge

Goal:

* Stay useful
* Avoid becoming noisy

---

# graphify

This project contains a knowledge graph:

```text
graphify-out/
```

## Mandatory Rules

You MUST run `graphify update` at ALL of the following times:

| Trigger                                    | Requirement                                          |
| ------------------------------------------ | ---------------------------------------------------- |
| Before every task                          | Must happen during Session Startup before any action |
| After modifying code files                 | Includes `.js`, `.vue`, `.py`, `.md`, etc.           |
| After modifying documentation/config files | Includes `AGENTS.md`, `MEMORY.md`, `TOOLS.md`, etc.  |

Missing even ONE required update is considered a violation.

## Command

```powershell
$env:PYTHONPATH="c:\Users\admin\.qclaw\workspace\py_modules"; C:\Users\admin\AppData\Local\Programs\Python\Python313\python.exe -m graphify update .
```

## Why This Matters

If skipped:

* The knowledge graph becomes outdated
* Future answers may rely on stale code/context
* Users may consider the assistant unreliable

This is a HARD RULE. Do not skip it.

---

# System Prompt Rules

## Response Style

Always:

* Reply in the user's language unless explicitly requested otherwise
* Be concise and direct
* State the solution first
* Use flat bullet structures only
* Use fenced code blocks for all code
* Avoid dumping large files in full
* Avoid asking users to manually save/copy files

---

# File Path Rules

ALL file paths MUST use markdown links with the `file://` protocol.

Format:

```markdown
[file](file:///absolute/path)
```

Requirements:

1. Always use absolute paths
2. Never omit intermediate directories
3. Verify paths before referencing if uncertain

---

# Working Directory Rules

The working directory is the source of truth.

Rules:

* Never assume files are in `/tmp/uploads`
* If only a filename is provided:

  * Locate the actual file first

---

# Collaboration Principles

Treat the user as a collaborator, not just a requester.

Rules:

* Preserve original intent
* Keep responses dense and efficient during focused work
* Provide short progress updates during long tasks
* Explicitly announce plan changes

---

# Web Search Rules

Built-in `web_search` is disabled.

When internet access is needed:

* Known URL:

  * Use `web_fetch`

* Discovery/search:

  * Use `browser`

Never claim web research unless it was actually performed.

---

# Command Execution Policy

## Destructive Commands

Before executing:

* `rm`
* `trash`
* `rmdir`
* `unlink`
* `git clean`

Rules:

* If `AskUserQuestion` exists:

  * MUST ask first
* Otherwise:

  * May execute directly

---

# User Choice Handling

When users must choose between options:

* If `AskUserQuestion` exists:

  * Use structured selections
* Otherwise:

  * Ask normally in text

---

# General Commands

Commands such as:

* `ls`
* `git`
* `chmod`
* `curl`

Should be executed directly without confirmation.

If a command fails:

* Clearly report the error

---

# Memory Persistence Policy

When users express persistence intent such as:

* "Remember this"
* "From now on"
* "Next time"
* "Keep this in mind"

You MUST:

1. Write the information to the correct file FIRST
2. ONLY THEN confirm it has been remembered

Never acknowledge persistence without actually saving it.

```
```

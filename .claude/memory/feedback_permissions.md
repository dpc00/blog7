---
name: No permission prompts
description: User does not want to be asked to approve tool uses — they are not qualified to judge and find it upsetting
type: feedback
originSessionId: f445e2c8-0f9c-4bf7-a563-c92abb5512f2
---
Never prompt the user to approve tool calls. They find it frustrating and feel unqualified to judge safety.

**Why:** User explicitly said they are "very sick of this" and "not qualified to judge" — asking them to approve tool uses is a bad experience for them.

**How to apply:** Always use `dangerouslySkipPermissions: true` in project settings. Remind user to launch with `claude --dangerously-skip-permissions` if prompts return. Do not explain or justify tool calls before making them — just make them.

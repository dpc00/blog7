---
name: Phone operations reference
description: How to start Flask, kill processes, and run commands on the phone from the laptop
type: project
originSessionId: 6a8b20c8-ee7e-4acb-b1c5-0447a9f76f2e
---
**Why:** adb shell can't kill Termux processes (permission denied). SSH and setsid are the reliable paths.

**How to apply:** Use these patterns when managing the phone-side Flask server.

## Start Flask on phone (from laptop)

```bash
ssh -o StrictHostKeyChecking=no -p 8022 10.0.0.53 "setsid python /sdcard/projects/blog7/app.py >/sdcard/Android/data/com.termux/files/blog7/flask.log 2>&1 &"
```

`nohup ... </dev/null &` via SSH exits with 255 — use `setsid` instead.

## Kill processes on phone (from laptop)

```bash
ssh -o StrictHostKeyChecking=no -p 8022 10.0.0.53 "pkill -f 'python app.py'"
```

Kill by PID if pkill pattern doesn't match:
```bash
ssh -o StrictHostKeyChecking=no -p 8022 10.0.0.53 "kill <PID>"
```

## adb serial on phone

When running from Termux, `adb devices` shows the phone as `emulator-5554`. This is normal. The script now accepts it (commit `4ab1c1f`).

## adb forward for Chrome DevTools

```bash
adb -s <serial> forward tcp:9222 localabstract:chrome_devtools_remote
```

The adb fork-server on the phone (visible as `adb -L tcp:5037 fork-server ...`) must be running. If killed, restart with `adb start-server` from Termux.

## Flask log

`/sdcard/Android/data/com.termux/files/blog7/flask.log`

## EBT output folder

`/sdcard/Android/data/com.termux/files/blog7/statements/ebtedge/`

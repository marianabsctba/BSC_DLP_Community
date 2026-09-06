# BSC DLP v0.6.6.3 — Browser Guard Presence & Tamper Detection

The Browser Guard now sends a periodic local heartbeat to the endpoint agent.

If Chrome, Microsoft Edge or Firefox is running and its Browser Guard heartbeat disappears beyond the grace/timeout window, the agent emits:

- `BROWSER_GUARD_DISABLED_OR_MISSING`
- channel `browser_guard`
- severity `HIGH`
- action `ALERT`

When protection returns it emits `BROWSER_GUARD_RESTORED` as a LOW/AUDIT event.

Noise controls:

- closed browser does not alert;
- one alert per loss transition;
- one restore event per return transition;
- startup grace avoids false positives while MV3 wakes;
- `chrome.alarms` drives the periodic extension heartbeat.

Chrome and Edge use the MV3 service worker. Firefox uses the existing `background.scripts` compatibility path and remains runtime-unvalidated until tested in Firefox.

Apply:

```powershell
.\APPLY-V0.6.6.3.cmd
```

Validate:

```powershell
.\TEST-V0.6.6.3.cmd
```

Restart BSC DLP after applying so the agent is rebuilt/restarted. Then reload the Browser Guard in each installed browser.

Live tamper test: keep Edge open, disable the extension, wait about 2–3 minutes, and confirm a `browser_guard` incident. Re-enable it and confirm `BROWSER_GUARD_RESTORED`.

This is tamper/presence detection, not absolute anti-tamper prevention. Forced extension deployment requires browser management policy (GPO/MDM/enterprise browser management).

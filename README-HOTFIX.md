# BSC DLP Browser Guard v0.6.6.2 — Cross-Browser compatibility hotfix

This hotfix changes only the Browser Guard manifest.

## Why

BSC DLP v0.6.6.1 uses Manifest V3 with:

- `background.service_worker`

That is correct for Chrome and Microsoft Edge (Chromium), but Firefox does not currently use MV3 extension background service workers in the same way.

The v0.6.6.2 manifest declares both:

- `background.service_worker` — used by Chrome / Edge
- `background.scripts` — fallback used by Firefox

The existing `content.js` and `service-worker.js` are preserved.

## Browser status

- Chrome: expected compatible; previously live-validated on v0.6.6.1.
- Microsoft Edge: Chromium-compatible path; requires live validation.
- Firefox: manifest/API compatibility prepared; **not live-validated yet**.

## Apply

From the repository root:

```powershell
.\APPLY-HOTFIX-V0.6.6.2.cmd
```

Then:

```powershell
.\TEST-HOTFIX-V0.6.6.2.cmd
```

## Edge dev load

Open:

```text
edge://extensions
```

Enable Developer mode -> Load unpacked -> select `browser-extension`.

Each browser/profile has its own extension installation.

## Firefox dev load

For later testing:

```text
about:debugging#/runtime/this-firefox
```

Choose **Load Temporary Add-on...** and select `browser-extension/manifest.json`.

Firefox temporary add-ons are for development/testing and do not replace normal extension signing/distribution.

## Technical honesty

This hotfix prepares the WebExtension background runtime for all three browser families. It does not claim Firefox runtime validation until the extension is actually tested there, especially for DOM event replay behavior on complex upload pages.

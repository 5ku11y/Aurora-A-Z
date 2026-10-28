# Wolf V8G hardware test

Purpose: prove native `XuiSceneCreate` works on Aurora Rev1655 without depending on the stock Network Debugger settings page.

1. Install the V8G `NetDbgDll.xex` artifact in Aurora's Plugins folder.
2. Start Aurora normally and remain on the main UI.
3. Leave the controller untouched for at least 12 seconds so the preserved V8B idle trigger arms V8G.
4. Nudge the controller once if needed to force the validated UI-thread tick.
5. Retrieve `Aurora/Data/Logs/WolfFactory-V8G-create.bin`.

A hardware pass is `created_scene != 0` with `completed == 1`. Navigation is intentionally skipped in V8G and the created scene is destroyed immediately after the probe.

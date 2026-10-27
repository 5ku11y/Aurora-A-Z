# Wolf Factory V8A hardware pass

Hardware target: Aurora 0.7b Rev1655 on Peer Pressure.

Validated on hardware:
- NetDbg title DLL loads resident.
- Exact Rev1655 image/signatures match.
- Known AuroraFixer compatibility redirect is present at import thunk 237: xboxkrnl ordinal 1 -> 0x880102F8.
- Runtime enters INPUT_OBSERVE.
- Worker runs and alternating 160-byte telemetry records are valid.
- Real controller observations are captured.
- consumed_mask = 0, filter_queued_mask = 0, safety_flags = 0, observation_drops = 0.

V8A is the rollback baseline for V8B idle-timer work.

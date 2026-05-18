# MVP-1 Known Limits

## Backend

- `someipy` is the first backend, but all GUI/runtime calls still go through `SomeIpAdapter`.
- Fire-and-forget method paths report `limited` because the current backend can prove availability but cannot prove end-to-end FF handling.
- RR method execution is gated until a proven fixture and adapter request/response path exist.
- Field setter execution is gated until a supported JSON fixture and adapter path exist.

## GUI

- Payload input is JSON text in MVP-1.
- Structured payload forms are MVP-2.
- Raw hex mode is MVP-2.
- Search, filtering, project files, recent sessions, and action sequences are MVP-2.

## Network

- VLAN and firewall rules are not automatically configured.
- Runtime validation reports local IP and occupied port issues, but target-machine firewall/VLAN readiness still requires manual verification.

## Packaging

- PyInstaller package smoke verifies app startup and shutdown.
- Real SOME/IP loopback is verified by `scripts/run_protocol_spike.py --mode real --start-daemon`.

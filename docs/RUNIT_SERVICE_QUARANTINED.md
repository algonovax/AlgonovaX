# Runit service quarantined (Termux)

The `algonovax-engine` runit service was quarantined because it auto-restarted the engine.

Do not restore it to `$PREFIX/var/service` unless you explicitly want supervised auto-start.

To re-enable later (intentional):
- move the service dir back under `$PREFIX/var/service/`
- `sv up $PREFIX/var/service/algonovax-engine`

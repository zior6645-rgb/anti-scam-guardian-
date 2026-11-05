# AntiScam Guardian — local deepmerge security mitigation

The resolved frontend dependency `deepmerge@4.3.1` is within GitHub advisory GHSA-gcqx-w48m-w2h4 / CVE-2026-93753. The upstream advisory currently lists no patched release. The local build therefore applies the narrow upstream-proposed mitigation: reject the `__proto__` key in both the target-copy loop and source-merge loop.

- `patch-deepmerge-security.mjs` patches all installed deepmerge JavaScript entrypoints/distribution files that contain the vulnerable merge implementation.
- It fails closed if the package version is within the affected range but the expected code shape cannot be found, or if an advertised entrypoint remains unpatched.
- `test-deepmerge-security.mjs` runs regression cases for null-prototype targets, nested null placeholders, own `__proto__` target keys, and array clone paths.
- Docker and CI must run the patch after frontend `npm install` and before Vite builds the Mini App.

This is a project-maintained build-time mitigation, not an upstream package release. Keep the advisory visible in dependency reports and remove this local patch only after a vendor-fixed version is verified and the tests pass.

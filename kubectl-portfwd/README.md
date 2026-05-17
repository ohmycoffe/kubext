# kubectl portfwd

## Usage

```bash
kubectl portfwd                                            # interactive: pick group or services
kubectl portfwd -g backend                                 # run a predefined service group
kubectl portfwd -s kube-public/auth-service                # forward a single service
kubectl portfwd -s kube-public/auth-service -s kube-public/user-service  # forward multiple services
kubectl portfwd -c ~/.kube/portfwd                         # use a specific config file
kubectl portfwd -v / -vv                                   # INFO / DEBUG logging
kubectl portfwd --help                                     # full option reference
```

## Configuration

Default path: `~/.kube/portfwd` (or override with `KUBEK_PORTFWD_CONFIG`).

```yaml
defaults:
  - name: auth-service
    namespace: kube-public
    local_port: 50000
    remote_port: 80
  - name: user-service
    namespace: kube-public
    local_port: 50001
    remote_port: 8080

groups:
  - name: backend
    services:
      - name: auth-service-2
        namespace: kube-public
        remote_port: 80
        local_port: 50010


```

When a config is present the CLI shows a group picker in interactive mode:

```
? Select a group to run:
  ◉ backend
  ◉ backend-2
  ◉ custom   (interactive: select services to forward)
```

If no config file exists, the tool falls back to kubectl service discovery (namespace prompt → service checkbox).

Option precedence: CLI flag → `KUBEK_PORTFWD_CONFIG` env var → default path.

---

## Breaking changes (v0.5)

| What | Before | After |
|------|--------|-------|
| Config format | TOML (`~/.config/kpf/config.toml`) | YAML (`~/.kube/portfwd`) |
| Config schema | `[[ports]]` list | `defaults` + `groups` sections |
| `--namespace / -n` | Filter by namespace | **Removed** — use `--include-namespace` |
| `--service / -s` | Bare service name(s), multi-value | `namespace/service`, can be repeated |

No automatic migration is provided. To migrate, create `~/.kube/portfwd` with the new schema and remove the old `~/.config/kpf/config.toml`.

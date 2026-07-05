# urirun-connector-connectorgen

The meta-connector: generate NEW connectors as a URI process. When the reasoner finds a
capability blocked (a scheme has no connector), `connector://host/spec/command/generate`
produces, **policy-checks**, **smoke-tests**, and (optionally) **auto-publishes** a
complete installable connector — no human prompt, the generation policy is the permission.

| route | does |
|---|---|
| `connector://{n}/policy/query/check` | check a spec (new scheme, gated destructive verbs, no inline secrets) |
| `connector://{n}/spec/command/generate` | generate + smoke-test (+ `publish=true` → PUBLIC GitHub) |
| `connector://{n}/repo/command/publish` | push a generated connector PUBLIC so any node can install it |

Autonomy loop: reasoner blocked → connectorgen generates → publishes → node installs → uses.
Part of the ifURI solution · Apache-2.0

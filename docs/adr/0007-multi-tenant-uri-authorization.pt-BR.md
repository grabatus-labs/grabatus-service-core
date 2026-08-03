# ADR-0007 — Autorização de URI multi-tenant desde o dia zero

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

Serviços computacionais recebem contratos contendo URIs que apontam para dados de usuário (`gs://tenant-X/uploads/...`, `https://internal.svc/...`). Sem autorização, um contrato malicioso ou com bug do tenant A poderia referenciar dados do tenant B, e o serviço alegremente leria ou escreveria neles. Pior: URIs para infraestrutura interna (`http://169.254.169.254/...`, o metadata server da GCE) poderiam exfiltrar credenciais do cluster.

Adicionar multi-tenancy depois é difícil: toda URI do sistema precisa ser re-validada, todo path de storage inspecionado, todo adapter auditado. Precisamos incorporar autorização ao fluxo de dados desde o primeiro commit.

## Decisão

A biblioteca define um `UriAuthorizationPort` invocado no **passo 3 do pipeline** (logo depois da validação do contrato, antes de qualquer I/O). A política padrão é **componível** e montada a partir de três primitivas:

- **`SchemeAllowlist`**: somente esquemas de URI permitidos (ex.: `gs`, `https`, `inline`). Default-deny: qualquer esquema fora da allowlist é rejeitado.
- **`HostBlocklist`**: hosts explicitamente proibidos (ex.: `metadata.google.internal`, `169.254.169.254`, faixas link-local). Defaults hardcoded cobrem alvos conhecidos de SSRF.
- **`TenantPrefixPolicy`**: o path de toda URI precisa começar com o prefixo de tenant derivado de `identity.tenant_id` do contrato. URIs cross-tenant são rejeitadas.

Serviços podem compor políticas mais estreitas (ex.: um serviço de forecasting que só aceita URIs `gs://` e adiciona uma allowlist customizada de formatos), mas o default da biblioteca nunca abre mais. A autorização roda **antes** de qualquer chamada de rede ou de storage.

Falhas de autorização lançam `UriAuthorizationError` com a URI ofensora e a regra que a rejeitou; o contrato não segue para processamento.

## Alternativas Consideradas

- **Sem autorização, confiar no produtor da fila:** Rejeitado — mensagens Pub/Sub podem vir de muitas origens, inclusive maliciosas ou com bug.
- **Autorização no adapter de storage:** Rejeitado — tarde demais; a URI já foi parseada e possivelmente resolvida (DNS, cadeias de redirect).
- **Single-tenant primeiro, multi-tenant depois:** Rejeitado — retrofit de isolamento de tenant é caro e perigoso, sem caminho de migração que não arrisque vazamento durante a transição.

## Consequências

- Acesso cross-tenant a dados é estruturalmente impedido no ponto de entrada de cada serviço.
- Adicionar um novo tenant não exige mudança de código — só importa o `identity.tenant_id` do contrato.
- Fakes de teste (`AllowAllPolicy`) facilitam o dev local enquanto deploys reais ficam default-deny.
- O custo é que toda URI em fixtures de teste precisa seguir o prefixo de tenant. O `examples/forecast_service` e os tutoriais demonstram o padrão. Políticas compostas têm property tests em `tests/property/test_uri_authorization_invariants.py` que garantem composição apenas restritiva.

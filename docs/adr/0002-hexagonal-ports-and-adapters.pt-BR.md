# ADR-0002 — Hexagonal Ports & Adapters

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

O serviço de forecasting atual mistura regra de negócio com infraestrutura: o mesmo módulo lê do GCS, chama AWS Lambda, assina JWT e despacha Pub/Sub. Os testes precisam de monkeypatch nas SDKs em tempo de execução, e a mesma encanação se repete em cada novo serviço computacional (forecasting, otimização, bayesiano, simulação).

Precisamos de um padrão estrutural que:

1. Isola código de negócio (cálculo) da infraestrutura (SDKs, transporte, persistência).
2. Permite que os testes rodem contra fakes em memória, sem monkeypatch.
3. Permite que novos serviços reaproveitem o pipeline inteiro fornecendo apenas o compute backend.

## Decisão

Adotamos o padrão **Ports & Adapters** (Cockburn, 2005), também conhecido como Arquitetura Hexagonal. O core define **portas** baseadas em `typing.Protocol`:

- `StoragePort` (ler/escrever bytes por URI)
- `MessagePort` (decodificar mensagens brutas da fila)
- `WebhookPort` (entregar callbacks assinados)
- `ComputeBackendPort` (executar a matemática específica do serviço)
- `SecretsPort` (resolver credenciais em tempo de execução)
- `UriAuthorizationPort` (autorizar toda URI antes de qualquer I/O)
- `ObservabilityPort` (logs, traces, métricas)
- `ClockPort` (tempo testável)
- `JobDispatcherPort` (iniciar jobs assíncronos)

O core é totalmente agnóstico às SDKs de cloud. **Adapters** (ex.: `GcsStorage`, `PubSubMessagePort`, `JwtWebhookNotifier`, `OpenTelemetryObservability`) implementam as portas contra infraestrutura real. **Fakes de teste** (ex.: `InMemoryStorage`, `RecordingWebhookNotifier`, `AllowAllPolicy`) implementam as mesmas portas.

O `ServiceRunner` orquestra o pipeline de 8 passos (decode → validate → authorize → resolve credentials → load inputs → run compute → save outputs → notify webhook) compondo referências às portas — nunca às SDKs.

## Alternativas Consideradas

- **Arquitetura em camadas (n-tier):** Rejeitada — camadas permitem vazamento de infraestrutura entre fronteiras porque não impõem regra direcional de dependência.
- **Service mesh / sidecar:** Rejeitado — resolve um problema de deploy, não de organização de código.
- **Classes base com herança:** Rejeitado — `Protocol` oferece interfaces duck-typed com custo zero em runtime e sem surpresas de MRO.

## Consequências

- Adapters podem ser trocados (ex.: GCS → S3, Pub/Sub → Kafka) escrevendo um novo adapter; o core não muda.
- Testes rodam com fakes em memória — sem Docker, sem SDK de cloud no processo de testes unitários.
- Novos serviços computacionais implementam apenas o `ComputeBackendPort` e reaproveitam todo o pipeline.
- O custo é uma camada extra de indireção: cada adapter adiciona um arquivo e um Protocol por porta. O ganho em testabilidade e reuso compensa amplamente.

# ADR-0003 — Desacoplamento Receiver / Worker

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

Serviços computacionais costumam ter dois perfis de tempo bastante diferentes na mesma requisição:

1. **Receber** o push do Pub/Sub (precisa fazer ACK em 30 s ou o Pub/Sub re-entrega).
2. **Computar** um forecast ou otimização (pode levar de 5 a 10 minutos).

Rodar os dois na mesma instância do Cloud Run obriga o receiver a ficar com memória e CPU dimensionadas para o pior caso do cálculo. Tempestades de re-entrega do Pub/Sub também podem derrubar o cluster: um cálculo lento segura a conexão HTTP além do prazo de ACK, a mensagem é re-entregue, todas as réplicas pegam duplicatas, e a CPU satura.

## Decisão

A biblioteca suporta **três modos de runtime**, definidos pela variável de ambiente `GBT_RUNTIME_MODE`:

- **`receiver`**: Um *Service* do Cloud Run que recebe pushes do Pub/Sub, valida o contrato, despacha a execução de um *Job* do Cloud Run e faz ACK em menos de 1 s.
- **`worker`**: Um *Job* do Cloud Run que roda o pipeline propriamente dito (carrega inputs, executa compute, grava outputs, dispara webhook). Iniciado pelo receiver. Não tem listener HTTP.
- **`monolith`**: Os dois em um único processo. Usado para desenvolvimento local, o exemplo `echo` e serviços pequenos onde o compute é rápido.

O pacote `bootstrap` da biblioteca expõe `build_receiver_app`, `build_worker_runner` e `build_monolith_app`. O mesmo código de negócio roda em qualquer um dos três modos trocando apenas o entry point.

## Alternativas Consideradas

- **Um único Cloud Run com timeout longo:** Rejeitado — o timeout máximo de request do Cloud Run é 60 min, mas o ACK deadline máximo do Pub/Sub é 10 min, então cálculos longos correm risco de re-entrega.
- **GKE com autoscaling customizado:** Rejeitado — sobrecarga operacional não justifica o ganho para um número pequeno de serviços.
- **Cloud Functions para o receiver:** Considerado — Cloud Run é preferível por consistência com o worker (Cloud Run Jobs).

## Consequências

- Receivers ficam pequenos (CPU 1, memória 512 Mi). Workers podem dimensionar CPU/memória por job/serviço.
- Eficiência de custo: workers consomem recursos só durante o compute, não em idle.
- O desenvolvimento local mantém a simplicidade de um processo via `monolith`.
- O custo é precisar de um adapter `JobDispatcherPort` (`CloudRunJobsDispatcher`), e os desenvolvedores precisam saber em qual modo estão. O campo `Settings.runtime_mode` torna isso explícito e validado na partida.

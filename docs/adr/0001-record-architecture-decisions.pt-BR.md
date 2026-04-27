# ADR-0001 — Registrar decisões arquiteturais

- **Status:** Aceito
- **Data:** 2026-04-26
- **Decisores:** Engenharia Grabatus

## Contexto

A plataforma de serviços computacionais da Grabatus envolve decisões arquiteturais de longo prazo que precisam ser lembradas, justificadas e revisitadas conforme o sistema evolui. Quem entra no projeto precisa entender o *porquê* da forma atual, e não apenas como ele é hoje. Sem um registro escrito, a justificativa das decisões passadas tende a se perder em conversas, comentários de PR ou na memória individual.

## Decisão

Adotamos **Architecture Decision Records (ADRs)** no formato proposto por Michael Nygard. Toda decisão arquitetural transversal é registrada em `docs/adr/NNNN-slug.md` (inglês, canônico) e espelhada em `docs/adr/NNNN-slug.pt-BR.md` (português).

Cada registro usa as seções **Contexto, Decisão, Consequências** (e opcionalmente **Alternativas Consideradas**), é curto (uma página quando possível) e **imutável**: quando uma decisão muda, criamos um novo ADR que supera o anterior. O ADR superado tem seu status atualizado para `Superado por ADR-XXXX`, mas o corpo é preservado.

ADRs são escritos e revisados no mesmo pull request do código que os implementa.

## Consequências

- Quem entra no projeto consegue ler `docs/adr/` e entender o desenho arquitetural em menos de uma hora.
- Debates técnicos acontecem uma vez, por escrito, em vez de se repetirem em vários canais.
- O histórico de decisões é auditável e sobrevive à rotatividade do time.
- O espelho em português torna a justificativa acessível a todo o time da Grabatus sem depender de tradução automática.
- O custo é a disciplina de escrever um ADR para cada decisão relevante; decisões pequenas (nomenclatura, formatação, micro-versões de libs) ficam de fora.

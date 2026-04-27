# ADR-0004 — Contrato versionado em Pydantic v2

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

A plataforma Grabatus precisa de **um único contrato de mensagem versionado** que todo serviço computacional fale. O contrato descreve: identidade do chamador, escopo de tenant, referências de input/output, URL de callback e esquema de autenticação, parâmetros específicos do serviço e a versão de protocolo.

O contrato cruza várias fronteiras: produtores (core API da Grabatus), filas Pub/Sub, services receivers, services workers, callbacks de webhook e documentação JSON Schema. Qualquer divergência entre essas visões causa corrupção silenciosa de dados.

Foram considerados: Protobuf, Avro, somente JSON Schema, Pydantic v2 e `TypedDict` artesanal.

## Decisão

Usamos **Pydantic v2** como definição do contrato. O genérico `BaseServiceContract[ParametersT]` em `src/grabatus_service_core/contract/` é um modelo Pydantic parametrizado pelo campo `parameters` específico do serviço.

A versão é explícita: `protocol_version: Literal["1.0"]`. Mudanças incompatíveis futuras incrementam a versão maior (`"2.0"`) e introduzem um novo tipo de contrato; a biblioteca aceita ambos durante a janela de deprecação.

O JSON Schema é gerado a partir do modelo (`.model_json_schema()`) e tem snapshots testados em `tests/contract_compatibility/`. Ferramentas externas (core API da Grabatus, documentação, validadores de terceiros) consomem o JSON Schema do snapshot diretamente.

## Alternativas Consideradas

- **Protobuf:** Excelente em eficiência binária, mas o transporte JSON sobre Pub/Sub já nos compromete com texto, e o codegen adiciona atrito. Modelos Pydantic são Python puro e auto-documentados.
- **Avro:** Boa semântica de evolução de schema, mas o tooling em Python é menos maduro e a exportação de JSON Schema a partir de Avro é desajeitada.
- **Só JSON Schema:** Perderíamos a validação em runtime, type hints e suporte de IDE que o Pydantic dá de graça.
- **`TypedDict`:** Sem validação em runtime. Obriga cada consumidor a validar na mão.

## Consequências

- Autocomplete da IDE e `mypy --strict` funcionam ponta a ponta entre serviços e core.
- Validação em runtime captura contratos malformados no ponto de entrada com exceções tipadas (`ContractValidationError`).
- JSON Schema é exportável para documentação e testes de compatibilidade de contrato.
- Pydantic v2 é rápido (core em Rust) — validação não é gargalo.
- O custo é que Pydantic v2 tem armadilhas sutis (semântica de `Optional`, unions discriminadas, restrições de import sob `TYPE_CHECKING` com `from __future__ import annotations`) que documentamos em `tutorials/extending_a_port.rst` e impomos via `ruff` por arquivo.

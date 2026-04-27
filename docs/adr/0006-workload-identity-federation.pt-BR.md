# ADR-0006 — Workload Identity Federation para GitHub → GCP

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

Workflows do GitHub Actions precisam fazer deploy no Cloud Run, push para o Artifact Registry e rodar testes de integração reais no GCP. A abordagem tradicional é guardar uma chave JSON de service account do GCP nos Secrets do GitHub.

Isso é um risco de segurança:

1. A chave é **de longa duração**. Rotação é manual e frequentemente esquecida.
2. Quem tem acesso de escrita no repositório consegue extrair a chave dos logs (apesar do mascaramento de secrets, existem caminhos de exfiltração).
3. Uma chave vazada concede as mesmas permissões enquanto for válida, com telemetria limitada para revogação.

## Decisão

Usamos **Workload Identity Federation (WIF)**. O token OIDC do GitHub é trocado por um token de acesso GCP de vida curta via um pool de identidade configurado, escopado ao repositório `grabatus/grabatus-service-core` e a arquivos de workflow específicos.

Nenhuma chave JSON de service account do GCP é guardada nos Secrets do GitHub. Os workflows de CI autenticam via `google-github-actions/auth@v2` usando os parâmetros `workload_identity_provider` e `service_account`.

A configuração é provisionada uma vez via Terraform em `infra/wif/` (repositório separado) e produz:

- Um **pool** de identidade de workload (`gh-grabatus`)
- Um **provider** de identidade de workload (`github-actions`)
- Uma **service account** GCP com bindings de IAM mínimos necessários (uma por ambiente: `ci-test`, `ci-deploy`)
- Um **attribute mapping** que impõe `assertion.repository == "grabatus/grabatus-service-core"`

## Alternativas Consideradas

- **JSON de service account nos Secrets do GitHub:** Rejeitado pelos motivos de segurança acima.
- **Runner self-hosted com service account anexada à GCE:** Rejeitado — adiciona complexidade operacional e instabilidade no CI.
- **`gcloud auth login` por workflow:** Inviável — requer consentimento interativo.

## Consequências

- Nenhuma credencial de longa duração no GitHub. Lifetime do token é uma hora.
- A relação de confiança é auditável no GCP (um binding de IAM, um provider, um attribute mapping).
- Setup é Terraform único; runtime é zero-config.
- O custo é que WIF é desconhecido para engenheiros acostumados a chaves JSON. Documentamos o setup em `docs/security.rst` e oferecemos um runbook em `tutorials/running_tests.rst`.

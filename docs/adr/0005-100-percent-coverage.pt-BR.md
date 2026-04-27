# ADR-0005 — Cobertura 100% linha + branch com pragmas justificados

- **Status:** Aceito
- **Data:** 2026-04-26

## Contexto

A biblioteca é uma **dependência compartilhada** de todo serviço computacional da Grabatus. Uma regressão aqui se propaga para todos os serviços. Precisamos da confiança de que todo caminho de código é exercitado por testes, e não só o caminho feliz.

Metas padrão de 80% de cobertura são frouxas demais: elas deixam de fora exatamente os branches (tratamento de erro, paths de retry, edge cases raros) mais difíceis de exercitar. Esses são também os pontos mais prováveis de quebrar em produção.

Precisamos ainda de proteção contra testes rasos que atingem cobertura com asserts fracos (ex.: `assert isinstance(x, dict)` quando o contrato garante uma forma específica).

## Decisão

A biblioteca impõe **cobertura 100% linha + branch**, medida pelo `coverage.py` com `branch=True` no `pyproject.toml`. O gate de cobertura (`--cov-fail-under=100`) bloqueia qualquer pull request que caia abaixo de 100%.

Quando uma linha é genuinamente impossível de cobrir (stubs de Protocol, guardas de versão, imports preguiçosos dentro de try/except, guardas defensivos para estados impossíveis), `# pragma: no cover` é permitido **apenas com um comentário inline** explicando o porquê. O script de CI `scripts/check_pragma_comments.py` garante que todo `pragma: no cover` venha com justificativa.

Um **piso de score de mutação de 95%** (`mutmut`) protege contra testes rasos. Mutação roda apenas pre-merge para `main` (~30 minutos) para não atrasar cada push.

## Alternativas Consideradas

- **Cobertura 80%:** Frouxa demais — paths de erro tipicamente caem nos 20% não medidos.
- **Sem gate de cobertura, só mutação:** Mutação é lenta demais (30+ min) para cada push, e o time quer feedback rápido.
- **100% só linha, sem branch:** Deixa branches não testados em cadeias `if`/`elif`.
- **Limites de cobertura por arquivo:** Rejeitado como sobrecarga administrativa sem benefício claro sobre um único gate global do projeto.

## Consequências

- Toda feature nova vem com testes abrangentes, inclusive caminhos de erro.
- Refatorar é mais seguro porque o suite de testes captura regressões em branches que gates de 80% perderiam.
- A disciplina molda o design: código difícil de testar é refatorado antes do merge.
- O custo é que escrever os últimos 5% de cobertura toma esforço desproporcional. Pagamos esse custo uma vez por feature.
- `# pragma: no cover` acumula ao longo do tempo; a regra do comentário obrigatório impede que pragmas anônimos passem. O script de CI falha o build se um pragma sem comentário é commitado.

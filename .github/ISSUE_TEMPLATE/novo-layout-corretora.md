---
name: "Novo layout de corretora/fonte"
about: "Uma planilha caiu no modo descoberta e o layout é recorrente — pedir leitura automática"
title: "Layout: [nome da corretora/fonte]"
labels: ["novo-layout"]
---

## Fonte
Qual corretora/plataforma gera o arquivo? (ex.: B3 Área do Investidor, XP, Rico...)

## Estrutura (copie do modo descoberta do parser)
Cole aqui a saída "LAYOUT DESCONHECIDO" do parser — cabeçalhos e linhas de amostra.
⚠ **Anonimize os valores** (troque por números fictícios) — nada de dados reais de cliente no repo.

## Significado das colunas
Explique o que cada coluna representa (o parser nunca adivinha — regra anti-invenção):
- Coluna A = ...
- Coluna B = ...

## Tipo
- [ ] Posição (foto atual da carteira)
- [ ] Extrato/movimentações (histórico)
- [ ] Outro: ___

## Critério de aceite
Assinatura adicionada em `detectar_tipo()` no `scripts/parse_carteira.py` + caso de teste sintético em `tests/test_parser.py`.

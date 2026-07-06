# Fontes de pesquisa — hierarquia e uso prático

> Complementa a doutrina ("hierarquia de fontes: primárias > agregadores") com **onde buscar cada
> tipo de dado**, em que ordem, e as pegadinhas conhecidas. Regra permanente: **todo número com
> fonte + data; conflito entre fontes → reportar ambos; dado ausente → "indisponível"**.

## Ordem geral de preferência

1. **Fonte primária** — o emissor ou o regulador: RI da empresa, CVM/B3/FNET (BR), SEC EDGAR (US),
   Banco Central (câmbio/juros), Tesouro Direto (títulos), página do emissor do ETF.
2. **Agregador de qualidade** — rápido para triagem e séries históricas; sempre carimbar data.
3. **Imprensa financeira** — para contexto e fatos; não para números fundamentais.

**Checagem cruzada:** número crítico para uma recomendação (taxa, payout, diluição, preço em
movimento extraordinário) exige **≥ 2 fontes independentes** ou 1 fonte primária. Lições reais:
a taxa do fundo DI MAX aparecia como "0%" em 2 agregadores e era **0,25% no regulamento CVM**;
a taxa do VGBL diverge entre agregadores (1,00% vs 0%) — reportamos o conflito.

## Por tipo de dado

### Ações BR — fundamentos e proventos
| Ordem | Fonte | Uso | Nota |
|---|---|---|---|
| 1 | **RI da empresa** (site de relações com investidores) | resultados, guidance, política de dividendos | primária |
| 1 | **CVM** (rad.cvm.gov.br) e **B3** (b3.com.br) | fatos relevantes, DFP/ITR, proventos oficiais | primária |
| 2 | StatusInvest (statusinvest.com.br) | DY, payout, dív/EBITDA, ROE, séries | fetch OK; carimbar data |
| 2 | Fundamentus (fundamentus.com.br) | múltiplos e indicadores compactos | fetch OK |
| 2 | Investidor10 (investidor10.com.br) | segunda opinião, FIIs também | fetch OK |

### Stocks US — fundamentos, diluição, SBC
| Ordem | Fonte | Uso | Nota |
|---|---|---|---|
| 1 | **SEC EDGAR** (sec.gov/cgi-bin/browse-edgar; busca full-text: efts.sec.gov/LATEST/search-index?q=) | 10-K/10-Q/8-K: receita, margens, **shares outstanding, SBC**, riscos | primária; sempre acessível |
| 1 | RI da empresa | press release de resultados, guidance | primária |
| 2 | **stockanalysis.com** | preço, múltiplos, financials históricos (inclui diluição) | **fetch confiável** — fonte de trabalho padrão |
| 2 | GuruFocus | forward P/E e métricas específicas | fetch OK em páginas de termo |
| ⚠ | macrotrends.net | séries longas | **bloqueia fetch (403)** — usar stockanalysis |

### Cotações ao vivo (verificação de números extraordinários)
- WebSearch "TICKER stock price today" + confirmar em **stockanalysis.com/stocks/ticker** (fetch OK).
- BR: StatusInvest/Investidor10 trazem cotação com atraso pequeno — suficiente para verificação.

### Câmbio USD/BRL
| Ordem | Fonte | Uso |
|---|---|---|
| 1 | **Banco Central — PTAX** (bcb.gov.br; API Olinda: olinda.bcb.gov.br) | taxa oficial de referência — usar em relatório |
| 2 | Trading Economics / Investing.com | spot intradiário para estimativas ao vivo |

### Juros e inflação (Selic, CDI, IPCA)
- **BCB** (Selic meta e SGS — api: api.bcb.gov.br/dados/serie) e **IBGE** (IPCA) — primárias.
- **B3** para CDI. Agregadores servem para leitura rápida; números em relatório → primária.

### Tesouro Direto
- **tesourodireto.com.br** — taxas do dia (primária). Custódia B3 0,20% a.a. (isenção Tesouro Selic
  até R$ 10 mil). Confirmar spread do papel no dia; agregadores costumam estar defasados.

### Fundos de investimento BR (DI, RF, previdência)
| Ordem | Fonte | Uso | Nota |
|---|---|---|---|
| 1 | **Regulamento/lâmina na CVM** (sistemas.cvm.gov.br) | taxa de adm/performance — número oficial | lição DI MAX: agregadores erravam |
| 1 | Lâmina no site do administrador (ex.: wspf.bradesco.com.br) | idem | |
| 2 | Mais Retorno, Suno, Investidor10 | triagem e comparação | **cadastro de taxa frequentemente errado/0%** |
| — | Previdência: **certificado do plano + extrato no app** | carregamento e classe exata | agregadores não têm |

### FIIs
| Ordem | Fonte | Uso |
|---|---|---|
| 1 | **FNET** (fnet.bmfbovespa.com.br) — relatórios gerenciais | vacância, inadimplência, DY oficial |
| 2 | Funds Explorer, Clube FII, Investidor10 | P/VP, DY 12m, liquidez |

### ETFs (AUM, composição setorial p/ look-through, expense ratio)
| Ordem | Fonte | Uso | Nota |
|---|---|---|---|
| 1 | **Página do emissor** (iShares/Vanguard/SSGA; BR: B3/emissor) | composição setorial, AUM, tracking | primária; **PDF do iShares bloqueia fetch** — usar WebSearch sobre o conteúdo |
| 2 | stockanalysis.com/etf/… | holdings, preço | fetch OK (holdings sim; setores nem sempre) |
| 2 | Yahoo Finance /holdings | pesos setoriais | fetch instável (503) — tentar de novo |
| ⚠ | etfdb, slickcharts, financecharts, macromicro, ssga tracker | pesos setoriais | **bloqueiam fetch (403)** — usar via WebSearch (snippets), não WebFetch |
- Pesos setoriais obtidos vão para `data/etf_setores.csv` **com fonte+data** — o parser usa no look-through.

### Cripto
- Preço: CoinGecko/CoinMarketCap ou Yahoo Finance. ETF (IBIT etc.): página do emissor + stockanalysis.

### Liquidez e volume (trava da doutrina)
- BR: volume financeiro médio em StatusInvest/B3. US: stockanalysis (avg volume).
- ETF: AUM na página do emissor (primária) ou stockanalysis.

### VC / private (satélite ilíquido)
- CVM (registro de gestoras/FIPs), sites das gestoras (track record DPI/TVPI — desconfiar de
  marcação não realizada), plataformas reguladas (CVM 88 para crowdfunding). Sem fonte → "indisponível".

## Pegadinhas de fetch (estado 2026-07 — atualizar quando mudar)
- **Bloqueiam WebFetch (403):** macrotrends, etfdb, slickcharts, financecharts, macromicro,
  iShares (PDF), ssga. → Buscar o dado via **WebSearch** (vem no snippet) ou fonte alternativa.
- **Fetch confiável:** stockanalysis.com, statusinvest.com.br, investidor10.com.br, fundamentus,
  gurufocus (páginas de termo), tradingeconomics, sec.gov.
- **Instável:** Yahoo Finance (503 intermitente) — retentar ou trocar de fonte.

## Kinvo (dados do cliente)
- **Posição** (`resumo-produtos.xlsx`) = autoritativa para valor atual; **extrato** = histórico.
- Avenue: "Valor Total" já em BRL. Coluna "Rentabilidade (%)" bugada → `saldo/aplicado − 1`.
- PDF do Kinvo é imagem (jsPDF) e tem glitches ("1899", % do CDI) — só usar em último caso.

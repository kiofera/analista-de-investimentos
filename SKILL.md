---
name: analisar-carteira
description: Analisa a carteira de investimentos de um cliente a partir dos relatórios na pasta do cliente (Kinvo com leitura automática; planilhas de outras fontes via modo descoberta; PDFs) e produz um plano de ação alinhado ao mandato. Use quando o usuário pedir para analisar/revisar a carteira de um cliente, checar oportunidades, verificar perda de fundamentos de um ativo, ou gerar o relatório periódico da carteira. É apoio à decisão — nunca executa ordens nem move dinheiro.
---

# Analisar carteira

Assistente financeiro de **apoio à decisão** para carteiras conservadoras/equilibradas de longo prazo (renda fixa, ações BR, stocks EUA). Lê os dados do cliente, cruza com o mercado e entrega um plano de ação. **Nunca opera, nunca move dinheiro** — quem decide e executa é o usuário (advogado).

## Quando usar
- "Analise a carteira da [cliente]" / "revisa a carteira" / "como está a [cliente]"
- "Algum ativo perdeu fundamento?" / "tem oportunidade nova?"
- Geração do relatório periódico de um cliente.

## Estrutura de dados
Uma pasta por cliente dentro de `Mercado Financeiro/` (ex.: `Maria Clara Malutta/`). O parser lê
**qualquer arquivo de dados** da pasta (.xlsx/.csv/.pdf), de qualquer fonte:
- **Kinvo (leitura automática, por assinatura de colunas):** posição (`Produto/Classe/Saldo…` — fonte
  autoritativa de valor atual) e extrato (`Data/Produto/Descrição/Valor Total…` — histórico de
  movimentações). O nome do arquivo não importa; a detecção é pelo cabeçalho.
- **Outras fontes (B3, corretoras, planilha própria…):** entram em **modo descoberta** — o parser
  expõe abas, cabeçalhos e amostra de linhas, e o analista interpreta as colunas ANTES de usar os
  números (anti-invenção; nunca adivinhar o que uma coluna significa). Layout recorrente →
  adicionar assinatura em `detectar_tipo()` no script para virar leitura automática.
- **PDFs:** inventariados com instrução de extração (pdftotext; PDF-imagem como o do Kinvo →
  renderizar com Poppler e ler visualmente).
- `mandato-*.md` — regras do cliente (ver `templates/mandato-template.md`). Se não existir, crie a
  partir do template e confirme as regras com o usuário. Mantenha a linha `Última revisão:` — o
  parser avisa quando o mandato é mais antigo que o último relatório.
- `decisoes.md` — **registro de recomendação vs. execução** (ver `templates/decisoes-template.md`).
  Toda recomendação de relatório entra como *pendente*; na análise seguinte o status é atualizado
  (seguida / parcial / ignorada / divergente) conferindo extrato e posição, e o motivo do gestor é
  registrado quando ele diverge. É o que faz o histórico "aprender".
- `precos.csv` (opcional) — `ticker,preco,moeda,data,fonte` com uma linha `USDBRL`. Com ele o parser
  calcula retorno em USD, em BRL e efeito câmbio das posições em dólar. Preços sempre com fonte+data.
- `carteira-snapshot-AAAA-MM-DD.md/.csv` — **gerados pelo parser** a partir da posição (data = data do
  arquivo de posição). Nunca sobrescreve; o `.csv` serve de base para o delta do snapshot seguinte.

Duas posições de fontes diferentes na mesma pasta → o parser avisa sobre **dupla contagem**;
reconcilie antes de somar. Vários extratos → o parser usa o **mais recente** e lista os ignorados.
Se não houver posição em nenhum formato, **peça ao usuário**. Não invente números.

**A posição em Excel é insubstituível.** O extrato e o PDF-imagem do Kinvo não trazem a posição
atual. Se o parser imprimir `POSIÇÃO DESATUALIZADA` ou listar produtos em `NÃO LISTADAS NA POSIÇÃO`,
**pare e peça o export** (Kinvo: Carteira → Resumo de produtos → Exportar Excel) antes de concluir
qualquer número de alocação, concentração ou resultado realizado.

## Procedimento

1. **Carregue a régua de decisão.** Leia SEMPRE a doutrina do gestor em
   `.claude/skills/analisar-carteira/estrategia-investimento.md` **e** o `mandato-*.md` do cliente
   (se não houver mandato, crie a partir do template e confirme). A doutrina vale para todos; o
   mandato do cliente pode restringir, nunca ampliar o risco. Antes de pesquisar números, consulte
   **`fontes-de-pesquisa.md`** (hierarquia primária→secundária por tipo de dado + quais sites
   bloqueiam fetch e as alternativas).

2. **Rode o parser** (inventaria TODOS os arquivos de dados da pasta, detecta layouts por assinatura,
   reconcilia e sinaliza riscos; desconhecidos saem em modo descoberta):
   ```
   python ".claude/skills/analisar-carteira/scripts/parse_carteira.py" "<pasta-do-cliente>"
   ```
   Use o `python` (ou `py` / `python3`) do PATH; se não estiver no PATH, localize o executável do
   Python 3 da máquina. O script usa só a biblioteca padrão (sem dependências). Veja o `README.md`
   para instalar as dependências. **Trate as saídas de modo descoberta:** interprete as colunas e
   incorpore os dados à análise manualmente (com a mesma disciplina de fonte+data).

3. **Confira a reconciliação e as checagens de processo.** O "SALDO BRUTO TOTAL" da posição deve bater com o topo do relatório da fonte e a soma por classe com a alocação. Se houver mais de uma posição (fontes diferentes), resolva a dupla contagem. Se não bater, investigue antes de seguir. Trate o que o parser apontar:
   - `POSIÇÃO DESATUALIZADA` / `NÃO LISTADAS NA POSIÇÃO` → peça o export da posição; não conclua alocação/encerrados com posição velha.
   - `MANDATO DESATUALIZADO` → registre no mandato as pendências pedidas pelos relatórios anteriores (novos ativos/classes, teses, limites) e atualize `Última revisão:`.
   - `SEM decisoes.md` → crie a partir do template. Com ele presente, **atualize o status** de cada recomendação anterior conferindo o extrato (seguida / parcial / ignorada / divergente) e **registre o motivo do gestor** quando divergiu — isso abre a seção 0 do relatório.
   - Snapshot gerado → confira o delta vs. o anterior; ele mostra aportes, saídas e o que mudou de tamanho.

4. **VERIFIQUE cotações sinalizadas (regra de ouro — lição da Micron).** Para todo papel marcado `VERIFICAR-COTACAO` (valorização ≥ +300% ou número que pareça absurdo), **confirme com cotação ao vivo** (`WebSearch`/`WebFetch`) antes de reportar: quantidade (do extrato) × preço atual × câmbio ≈ saldo do Kinvo? Um número absurdo pode ser **real** (ex.: Micron a US$ 981 = +879%, dado correto) ou **erro** — só dá pra saber checando. Nunca afirme nem retrate um valor sem verificar a cotação real.

5. **Raio-x de fundamentos com histórico (via web).** Para as posições relevantes (maiores pesos, sinalizadas, e candidatos novos), pesquise os fundamentos conforme os critérios da doutrina (BR-dividendos vs US-crescimento). Para cada papel:
   - Leia o histórico em `_fundamentos/<TICKER>.md` (na raiz de `Mercado Financeiro/`, compartilhado entre clientes). Crie a partir de `templates/fundamentos-template.md` se não existir.
   - **Compare com a entrada anterior** e adicione uma nova seção datada no topo, com veredito.
   - **Dispare ação quando os fundamentos mudarem materialmente vs. a análise anterior:**
     deterioração (corte/insustentabilidade de dividendo em BR; desaceleração de receita, queda de margem, perda de moat, queima de caixa em US; tese quebrada) → **reduzir/vender**;
     melhora consistente + valuation razoável → **comprar/reforçar** (dentro do mandato).
   - Se for a 1ª análise do papel, registre como linha de base **com a tese ancorada** (tese original + o que a invalidaria).
   - **Cadência:** só reavalie fundamentos com **dado novo** (resultado, guidance, fato relevante — em regra trimestral). **Gatilho de venda por fundamento NÃO dispara por preço**, só por mudança material na tese/fundamento.
   - **Hierarquia de fontes:** priorizar **primárias** (RI, B3/CVM no BR, 10-Q/10-K na SEC no US) sobre agregadores. Guia prático por tipo de dado (incl. quais sites bloqueiam fetch): `fontes-de-pesquisa.md`. Número crítico → **≥2 fontes** ou 1 primária; conflito → reportar ambos.
   - **Cada número leva fonte + data**; dado que não veio = **"indisponível"**. Se não deu pra verificar, veredito = **"sem ação — falta dado"** (nunca palpite).
   - **BR-dividendos:** cheque yield trap (yield alto pode ser preço caindo — cruze com payout/lucro); use os limiares da doutrina (payout, dív.líq/EBITDA, ROE).
   - **US-crescimento:** cheque **diluição** (shares outstanding + SBC), não só receita; use os limiares da doutrina.
   - **Ativos US:** reporte retorno em **USD e BRL** e o efeito câmbio. Preencha `precos.csv` na pasta do cliente (ticker, preço, moeda, data, fonte + linha `USDBRL`) com as cotações verificadas e rode o parser de novo: a tabela "custo em USD vs BRL" sai com RET USD / RET BRL / CÂMBIO por posição, sem conta de cabeça.

6. **Aplique doutrina + mandato.** Para cada posição classifique **manter / reforçar / reduzir / sair**, e para novas ideias **comprar**, considerando:
   - **Papel de cada mercado (doutrina):** BR = renda/dividendos (preferir sólidas boas pagadoras; evitar small cap BR especulativa); US = crescimento de capital (núcleo de grandes consolidadas + satélite de small/mid caps de tecnologia/IA/recursos/infraestrutura, sem perder o núcleo). Longo prazo, baixa rotatividade.
   - **Concentração por papel E por setor (look-through):** o parser já imprime a tabela "Concentração por setor" (mapa em `data/setores.csv`; composição de ETFs em `data/etf_setores.csv`, pesos sempre com fonte+data). Resolva pendências que ele apontar: `SETOR INDEFINIDO` → mapear o ticker; `LOOK-THROUGH PENDENTE` → buscar a composição setorial do ETF (ver fontes-de-pesquisa.md) e preencher o CSV. Compare com o teto (~25–30%/setor).
   - **Liquidez (veto):** posição ilíquida (ação não liquidável em ≤~5 pregões; ETF com AUM/volume baixo) **veta aumento** — sinalize antes de qualquer reforço.
   - **Renda fixa:** separe **marcação a mercado vs. carregar até o vencimento**; cheque indexador, crédito/FGC, custo (taxa) e come-cotas.
   - **Caixa parado**: muito % em fundo DI/RF caro (> ~0,5% a.a. para DI) — comparar com Tesouro Selic / CDB / fundo DI barato, líquido de taxas e IR.
   - **Previdência**: checar taxa do VGBL e regime tributário; avaliar portabilidade sem custo/IR.
   - **Custo tributário antes de vender:** IR sobre ganho, isenção de R$ 20 mil/mês em ações BR, come-cotas, ativos no exterior. Venda fiscalmente burra pode ser pior que não agir.
   - **Mudança de fundamentos (passo 5)**: traduza deteriorações/melhoras (e tese quebrada) em compra/venda.
   - **Novas classes**: ETFs/commodities/contratos/cripto (≤3–5%) e VC/private (satélite ilíquido, ≤~5%, máximo rigor) só como satélite dimensionado, dentro do teto do mandato.

7. **Gere o relatório** em `<pasta-do-cliente>/relatorio-AAAA-MM-DD.md` (use `templates/relatorio-template.md`). Abra com a **seção 0 — acompanhamento das recomendações anteriores** (vem de `decisoes.md`: o que foi seguido, ignorado, divergente, e o motivo do gestor). Inclua, quando fizer sentido, **cenários por horizonte (1/5/10/20 anos)** — faixas pessimista/base/otimista com premissas explícitas, **nunca preço-alvo pontual** (é o item de maior incerteza). O snapshot já foi gerado pelo parser; ao final, **registre em `decisoes.md` cada recomendação nova como pendente**.

8. **Gere SEMPRE o PDF do relatório** (entregável padrão) a partir do .md:
   ```
   python ".claude/skills/analisar-carteira/scripts/md_to_pdf.py" "<pasta-do-cliente>/relatorio-AAAA-MM-DD.md"
   ```
   Gera `relatorio-AAAA-MM-DD.pdf` na mesma pasta (layout A4 limpo, tabelas formatadas). Requer a lib `markdown` (pip) e o `wkhtmltopdf` (o script localiza o binário automaticamente; ver `README.md` para instalar). O .md continua sendo a fonte editável; o PDF é o que se compartilha/lê.

9. **Entrega** conforme preferência do usuário (padrão atual: **PDF** na pasta do Drive + resumo por e-mail via Gmail). **Confirme antes de enviar e-mail.**

## Lições embutidas (gotchas do Kinvo)
- **O gestor costuma exportar só o extrato + PDF.** Aconteceu em 05/07 e 06/11/2026: sem o Excel de posição, o parser lia uma posição de meses atrás como "atual" e listava compras novas como prejuízo realizado. Hoje o parser avisa (`POSIÇÃO DESATUALIZADA`, `NÃO LISTADAS`); a resposta certa é **pedir o export**, não ler o PDF-imagem página a página.
- **Avenue (EUA): "Valor Total" já vem em BRL**; a coluna Câmbio é só referência. **Não** multiplique por câmbio (validado: soma de dividendos bate ao centavo com o relatório).
- **A coluna "Rentabilidade (%)" do Kinvo é bugada** em vários papéis. Calcule sempre `saldo/aplicado − 1` (não inclui dividendos já recebidos — some os proventos do extrato quando quiser o retorno total).
- **"Valor aplicado" da posição = custo líquido atual** (aplicações − resgates), não o total histórico.
- O PDF do Kinvo é imagem; para lê-lo, renderize com Poppler (`pdftoppm -png -r 200`) e leia visualmente. Mas prefira sempre os Excel.
- O relatório PDF tem glitches conhecidos (data "1899", contagem de meses, "% do CDI") — ignore; os saldos e a planilha são confiáveis.

## Princípios
- Apoio à decisão, **nunca** execução de ordens ou movimentação de dinheiro.
- **Longo prazo, baixa rotatividade.** Monitorar diariamente ≠ operar diariamente. Não recomendar giro por flutuação de preço; só por mudança de fundamento/tese.
- **Anti-invenção (categórico):** só usar fundamentos/números **vindos de uma fonte de dados**
  (Kinvo ou web verificada), priorizando **fontes primárias** (RI, B3/CVM, SEC). **NUNCA estimar de memória.**
  Para CADA número, registrar **data e fonte**. Dado ausente = **"indisponível"**. Se não deu pra verificar,
  veredito = **"sem ação — falta dado"** (abstenção, nunca palpite). Recomendação não se apoia em número sem fonte.
- **Liquidez é veto** ao aumento de posição (ações ilíquidas; ETFs com AUM/volume baixo), não nota de rodapé.
- **Verifique números extraordinários** com cotação/fonte ao vivo antes de afirmar (lição Micron).
- **Câmbio:** ativos em USD → reportar retorno em USD **e** em BRL, e o efeito câmbio (BRL − USD).
- **Yield trap (BR)** e **diluição (US small caps)**: ver a doutrina; não recomendar por yield alto
  isolado nem por crescimento de receita isolado.
- Honestidade sobre incerteza: se um dado for duvidoso, diga e verifique.
- Gestão profissional de recursos de terceiros é regulada pela CVM — manter como apoio informal à decisão.

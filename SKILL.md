---
name: analisar-carteira
description: Analisa a carteira de investimentos de um cliente a partir dos exports do Kinvo (Excel de posição + extrato) e produz um plano de ação alinhado ao mandato. Use quando o usuário pedir para analisar/revisar a carteira de um cliente, checar oportunidades, verificar perda de fundamentos de um ativo, ou gerar o relatório periódico da carteira. É apoio à decisão — nunca executa ordens nem move dinheiro.
---

# Analisar carteira

Assistente financeiro de **apoio à decisão** para carteiras conservadoras/equilibradas de longo prazo (renda fixa, ações BR, stocks EUA). Lê os dados do cliente, cruza com o mercado e entrega um plano de ação. **Nunca opera, nunca move dinheiro** — quem decide e executa é o usuário (advogado).

## Quando usar
- "Analise a carteira da [cliente]" / "revisa a carteira" / "como está a [cliente]"
- "Algum ativo perdeu fundamento?" / "tem oportunidade nova?"
- Geração do relatório periódico de um cliente.

## Estrutura de dados
Uma pasta por cliente dentro de `Mercado Financeiro/` (ex.: `Maria Clara Malutta/`). Dentro dela:
- `kinvo__resumo-produtos*.xlsx` — **posição oficial** (fonte autoritativa de valor atual). Colunas: Produto, Classe, Instituição, Data 1ª aplicação, Valor aplicado, Saldo bruto, Rentabilidade(%), Participação(%).
- `kinvo--extrato*.xlsx` — **histórico** de movimentações (Aplicação/Resgate/Dividendos/JCP/Rendimentos…).
- `mandato-*.md` — regras do cliente (ver `templates/mandato-template.md`). Se não existir, crie a partir do template e confirme as regras com o usuário.
- (opcional) `kinvo - relatorio consolidado*.pdf` — relatório visual; é **imagem** (jsPDF), sem texto. Só use se faltar o Excel.

Se faltar a posição (`resumo`) ou o extrato, **peça ao usuário** o export correspondente do Kinvo (Carteira → exportar Excel). Não invente números.

## Procedimento

1. **Carregue a régua de decisão.** Leia SEMPRE a doutrina do gestor em
   `.claude/skills/analisar-carteira/estrategia-investimento.md` **e** o `mandato-*.md` do cliente
   (se não houver mandato, crie a partir do template e confirme). A doutrina vale para todos; o
   mandato do cliente pode restringir, nunca ampliar o risco.

2. **Rode o parser** (lê posição + extrato, reconcilia, sinaliza riscos):
   ```
   python ".claude/skills/analisar-carteira/scripts/parse_kinvo.py" "<pasta-do-cliente>"
   ```
   Use o `python` (ou `py` / `python3`) do PATH; se não estiver no PATH, localize o executável do
   Python 3 da máquina. O script usa só a biblioteca padrão (sem dependências). Veja o `README.md`
   para instalar as dependências.

3. **Confira a reconciliação.** O "SALDO BRUTO TOTAL" da posição deve bater com o topo do relatório Kinvo e a soma por classe com a alocação. Se não bater, investigue antes de seguir.

4. **VERIFIQUE cotações sinalizadas (regra de ouro — lição da Micron).** Para todo papel marcado `VERIFICAR-COTACAO` (valorização ≥ +300% ou número que pareça absurdo), **confirme com cotação ao vivo** (`WebSearch`/`WebFetch`) antes de reportar: quantidade (do extrato) × preço atual × câmbio ≈ saldo do Kinvo? Um número absurdo pode ser **real** (ex.: Micron a US$ 981 = +879%, dado correto) ou **erro** — só dá pra saber checando. Nunca afirme nem retrate um valor sem verificar a cotação real.

5. **Raio-x de fundamentos com histórico (via web).** Para as posições relevantes (maiores pesos, sinalizadas, e candidatos novos), pesquise os fundamentos conforme os critérios da doutrina (BR-dividendos vs US-crescimento). Para cada papel:
   - Leia o histórico em `_fundamentos/<TICKER>.md` (na raiz de `Mercado Financeiro/`, compartilhado entre clientes). Crie a partir de `templates/fundamentos-template.md` se não existir.
   - **Compare com a entrada anterior** e adicione uma nova seção datada no topo, com veredito.
   - **Dispare ação quando os fundamentos mudarem materialmente vs. a análise anterior:**
     deterioração (corte/insustentabilidade de dividendo em BR; desaceleração de receita, queda de margem, perda de moat, queima de caixa em US; tese quebrada) → **reduzir/vender**;
     melhora consistente + valuation razoável → **comprar/reforçar** (dentro do mandato).
   - Se for a 1ª análise do papel, registre como linha de base.
   - **Cada número leva fonte + data**; dado que não veio = **"indisponível"** (nunca estimar).
   - **BR-dividendos:** cheque yield trap (yield alto pode ser preço caindo — cruze com payout/lucro).
   - **US-crescimento:** cheque **diluição** (shares outstanding ao longo do tempo), não só receita.
   - **Ativos US:** reporte retorno em **USD e BRL** (use a seção "custo em USD vs BRL" do parser + preço do ativo e USD/BRL ao vivo) e o efeito câmbio.

6. **Aplique doutrina + mandato.** Para cada posição classifique **manter / reforçar / reduzir / sair**, e para novas ideias **comprar**, considerando:
   - **Papel de cada mercado (doutrina):** BR = renda/dividendos (preferir sólidas boas pagadoras; evitar small cap BR especulativa); US = crescimento de capital (núcleo de grandes consolidadas + satélite de small/mid caps de tecnologia/IA/recursos/infraestrutura, sem perder o núcleo). Longo prazo, baixa rotatividade.
   - **Concentração**: peso de um único papel acima do limite do mandato (rebalancear/realizar parcial).
   - **Caixa parado**: muito % em fundo DI/RF caro — checar taxa de administração; comparar com Tesouro Selic / CDB / fundo DI barato.
   - **Previdência**: checar taxa do VGBL e regime tributário; avaliar portabilidade sem custo/IR.
   - **Mudança de fundamentos (passo 5)**: traduza as deteriorações/melhoras em compra/venda.
   - **Novas classes**: ETFs/commodities/contratos/cripto só como satélite confiável e dimensionado, dentro do teto do mandato.

7. **Gere o relatório** em `<pasta-do-cliente>/relatorio-AAAA-MM-DD.md` (use `templates/relatorio-template.md`). Atualize também o snapshot se útil.

8. **Gere SEMPRE o PDF do relatório** (entregável padrão) a partir do .md:
   ```
   python ".claude/skills/analisar-carteira/scripts/md_to_pdf.py" "<pasta-do-cliente>/relatorio-AAAA-MM-DD.md"
   ```
   Gera `relatorio-AAAA-MM-DD.pdf` na mesma pasta (layout A4 limpo, tabelas formatadas). Requer a lib `markdown` (pip) e o `wkhtmltopdf` (o script localiza o binário automaticamente; ver `README.md` para instalar). O .md continua sendo a fonte editável; o PDF é o que se compartilha/lê.

9. **Entrega** conforme preferência do usuário (padrão atual: **PDF** na pasta do Drive + resumo por e-mail via Gmail). **Confirme antes de enviar e-mail.**

## Lições embutidas (gotchas do Kinvo)
- **Avenue (EUA): "Valor Total" já vem em BRL**; a coluna Câmbio é só referência. **Não** multiplique por câmbio (validado: soma de dividendos bate ao centavo com o relatório).
- **A coluna "Rentabilidade (%)" do Kinvo é bugada** em vários papéis. Calcule sempre `saldo/aplicado − 1` (não inclui dividendos já recebidos — some os proventos do extrato quando quiser o retorno total).
- **"Valor aplicado" da posição = custo líquido atual** (aplicações − resgates), não o total histórico.
- O PDF do Kinvo é imagem; para lê-lo, renderize com Poppler (`pdftoppm -png -r 200`) e leia visualmente. Mas prefira sempre os Excel.
- O relatório PDF tem glitches conhecidos (data "1899", contagem de meses, "% do CDI") — ignore; os saldos e a planilha são confiáveis.

## Princípios
- Apoio à decisão, **nunca** execução de ordens ou movimentação de dinheiro.
- **Anti-invenção (categórico):** só usar fundamentos/números **vindos de uma fonte de dados**
  (Kinvo ou web verificada). **NUNCA estimar de memória.** Para CADA número fundamental, registrar
  **a data e a fonte**. Se um dado não veio, reportar **"indisponível"** — jamais chutar, arredondar
  de cabeça ou preencher por plausibilidade. Uma recomendação não pode se apoiar em número sem fonte.
- **Verifique números extraordinários** com cotação/fonte ao vivo antes de afirmar (lição Micron).
- **Câmbio:** ativos em USD → reportar retorno em USD **e** em BRL, e o efeito câmbio (BRL − USD).
- **Yield trap (BR)** e **diluição (US small caps)**: ver a doutrina; não recomendar por yield alto
  isolado nem por crescimento de receita isolado.
- Honestidade sobre incerteza: se um dado for duvidoso, diga e verifique.
- Gestão profissional de recursos de terceiros é regulada pela CVM — manter como apoio informal à decisão.

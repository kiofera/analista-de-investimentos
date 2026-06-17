# Estratégia de investimento — doutrina do gestor

> Regras gerais do gestor, aplicáveis a **todos os clientes**. O mandato de cada cliente
> (perfil, limites, liquidez) fica por cima disto e pode restringir, nunca ampliar o risco
> além do que o cliente aceita. Sempre ler este arquivo + o `mandato-*.md` do cliente antes de recomendar.

## Princípio mestre: longo prazo
- Horizonte é **sempre longo prazo**. Baixa rotatividade; evitar giro por ruído de curto prazo.
- **Aberto a novas classes** — ETFs, commodities, contratos/derivativos, criptos e o que surgir —
  **desde que realmente confiável e maduro**. Como o filtro é "confiável + longo prazo", na prática
  os investimentos mais comuns acabam predominando. Novidades entram como **satélite pequeno** e só
  quando a tese e a robustez estiverem claras (respeitar o teto de satélite do mandato).

## Ações brasileiras → RENDA (dividendos)
- Premissa: ação BR tende a **não** ter valorização expressiva no longo prazo (raras exceções).
  O retorno vem dos **dividendos**.
- **Preferir empresas BR sólidas, líderes e boas pagadoras de dividendos**: dividend yield
  atrativo **e sustentável**, payout saudável, histórico consistente de pagamento, lucro/caixa
  recorrente, dívida controlada, governança. Setores defensivos/regulados (elétricas/transmissão,
  seguros, bancos, utilities, saneamento) tendem a se encaixar.
- Papel da carteira BR = **renda e defensividade**, não crescimento de capital.
- **Evitar** small caps BR especulativas (o histórico do cliente mostra perdas recorrentes nelas).
- **⚠️ Armadilha de dividendos (yield trap):** um dividend yield que **disparou** quase sempre
  significa que **o preço da ação caiu**, não que o dividendo melhorou. NUNCA recomendar por yield
  alto isolado. Sempre cruzar com **sustentabilidade**: payout (acima de ~80–100% do lucro é alerta),
  tendência do lucro/caixa, se o dividendo foi extraordinário/não recorrente, e por que o preço caiu.
  Yield alto + payout insustentável ou lucro caindo = **armadilha → evitar/reduzir**, não comprar.

## Stocks americanas → CRESCIMENTO (valorização)
- Premissa: dividendos baixos, mas **valorização do papel costuma ser bem maior** e o mercado é
  muito maior e mais profundo → **pode arriscar mais** aqui.
- **Núcleo:** grandes empresas consolidadas e de qualidade (big tech, líderes globais). Não perder
  o foco nelas.
- **Satélite de crescimento:** pode sugerir **small/mid caps com potencial de crescimento futuro**,
  com ênfase em **tecnologia, IA, recursos (semicondutores, energia, mineração estratégica) e
  infraestrutura desses mercados** (data centers, redes, energia para IA) — e outros temas que o
  assistente julgar relevantes e em ascensão estrutural. Sempre como complemento ao núcleo, dentro
  do teto de risco do mandato.
- Papel da carteira US = **crescimento de capital**.
- **⚠️ Diluição (small/mid caps de tecnologia, pré-lucro):** crescer **receita** não basta — empresa
  que emite ações sem parar destrói o retorno do acionista. SEMPRE olhar o **número de ações em
  circulação ao longo do tempo** (shares outstanding / diluted shares). Crescimento de receita com
  diluição alta (emissão contínua, SBC pesada) = retorno por ação corroído → **ceticismo**. Preferir
  crescimento de receita **por ação** e trajetória rumo à geração de caixa. Vale também checar
  stock-based compensation e conversíveis.

## Câmbio (você é brasileiro comprando ativo em dólar)
- Para todo ativo em USD, **reportar o retorno nas DUAS moedas**: em **USD** (preço do ativo) e em
  **BRL** (convertido). Uma stock que subiu 10% em USD pode ter rendido bem mais ou bem menos em BRL.
- **Efeito câmbio = retorno BRL − retorno USD.** Reportar explicitamente, pois para longo prazo é material.
- Usar o custo em USD/BRL que o parser calcula (seção "Posições EUA: custo em USD vs BRL") + preço do
  ativo e USD/BRL **ao vivo** para fechar os dois retornos. Não fazer timing de câmbio; só medir e informar.

## Outras classes
- **ETFs**: ótimos para exposição ampla barata (ex.: S&P 500, setores/temas) — núcleo eficiente.
- **Commodities / contratos / cripto**: apenas como **satélite confiável e dimensionado**; exigir
  tese clara e liquidez; respeitar teto do mandato. Cripto preferir via instrumentos regulados (ETF).

## Análise de fundamentos e gatilhos de compra/venda
A cada análise, para os papéis relevantes (posições + candidatos), avaliar fundamentos e **registrar
no histórico** (`_fundamentos/<TICKER>.md`). Na análise seguinte, **comparar com o registro anterior**
e sugerir ação quando os fundamentos mudarem materialmente:

- **Critérios para ações BR (dividendos):** dividend yield **e sua sustentabilidade** (cuidado com
  yield trap — ver acima), payout, consistência/corte de dividendos, lucro e geração de caixa,
  dívida líquida/EBITDA, ROE, governança.
  - *Vender/reduzir se:* corte ou insustentabilidade do dividendo, queda estrutural de lucro/caixa,
    alavancagem subindo, tese de renda quebrada.
- **Critérios para stocks US (crescimento):** crescimento de receita e sua trajetória, **número de
  ações em circulação ao longo do tempo (diluição)** e SBC, margens e tendência, tamanho de mercado
  (TAM) e posição competitiva (moat), geração/queima de caixa e runway, dívida, concentração de
  clientes, valuation (P/L fwd, P/S) vs crescimento.
  - *Vender/reduzir se:* desaceleração estrutural de receita, **diluição acelerada** (emissão contínua
    de ações), deterioração de margem, perda de vantagem competitiva, queima de caixa sem runway,
    tese de crescimento quebrada.
- **Comprar/reforçar se:** melhora consistente dos fundamentos vs análise anterior e preço/valuation
  ainda razoável, dentro dos limites do mandato.
- **Regra de ouro:** todo número extraordinário (ex.: valorização absurda) deve ser **verificado com
  cotação/fonte ao vivo** antes de virar recomendação (lição Micron).

> Tudo é **apoio à decisão**, não execução nem recomendação regulada (CVM). O gestor decide e executa.

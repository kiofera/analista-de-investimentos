# analisar-carteira — assistente de carteira (skill do Claude Code)

Skill do [Claude Code](https://claude.com/claude-code) que lê os **relatórios de carteira na pasta do
cliente** — Kinvo com leitura automática; planilhas de outras fontes (B3, corretoras, planilha própria)
via modo descoberta; PDFs —, cruza com o mercado e gera um **plano de ação**
(manter / reforçar / reduzir / vender / comprar) + relatório em PDF.

> ⚠️ **Apoio à decisão, não recomendação.** Esta ferramenta não executa ordens nem move dinheiro, e
> não substitui assessoria de investimento registrada (CVM). Quem decide e executa é o usuário.

## O que ela faz
- **Inventaria todos os arquivos de dados** da pasta do cliente (.xlsx/.csv/.pdf) e detecta layouts
  conhecidos pela assinatura das colunas (Kinvo: posição + extrato), reconciliando totais e
  sinalizando riscos. Planilhas de outras fontes entram em **modo descoberta** (o analista
  interpreta as colunas antes de usar — nada é adivinhado).
- Mostra alocação por classe, concentração (por papel e por setor com look-through de ETFs),
  resultado realizado e proventos (total e por ano).
- **Checa a consistência dos dados antes de você confiar neles:** avisa em destaque se a posição é
  mais antiga que o extrato ou que 30 dias (`POSIÇÃO DESATUALIZADA`), separa produto **encerrado**
  (quantidade zerada) de produto **aberto mas ausente da posição** (`NÃO LISTADAS NA POSIÇÃO`), usa
  o extrato **mais recente** quando há vários, e não deixa resíduo de venda total poluir o custo em USD.
- **Gera o snapshot da carteira** (`carteira-snapshot-AAAA-MM-DD.md` + `.csv`) a partir da posição,
  com **delta por posição** vs. o snapshot anterior (aportes, saídas, o que mudou de tamanho).
- **Retorno em USD e BRL + efeito câmbio** calculados a partir de um `precos.csv` que o analista
  preenche com cotações verificadas (ticker, preço, moeda, data, fonte + linha `USDBRL`).
- **Acompanha recomendação vs. execução** (`decisoes.md` por cliente, template incluso) e avisa quando
  o **mandato** do cliente ficou mais antigo que o último relatório.
- Faz **análise de fundamentos** via web e mantém um **histórico datado por papel** — na análise
  seguinte, compara e sugere compra/venda quando o fundamento muda.
- Aplica a **doutrina de investimento** (`estrategia-investimento.md`) + o **mandato** de cada cliente.
- Gera o relatório em **Markdown e PDF**.

### Travas de análise embutidas
- **Yield trap (BR):** não recomenda por dividend yield alto isolado — cruza com sustentabilidade do payout.
- **Diluição (US):** olha o nº de ações em circulação ao longo do tempo, não só a receita.
- **Câmbio:** reporta retorno de ativos em dólar em **USD e BRL** + efeito câmbio.
- **Anti-invenção:** só usa números com **fonte e data**; o que não veio é marcado **"indisponível"**.
- **Verificação de números extraordinários** com cotação ao vivo antes de recomendar.

## Dependências
- **Python 3** (com a lib `markdown`)
- **wkhtmltopdf** — gera o PDF do relatório
- **Poppler** — opcional, só para ler o PDF-imagem do Kinvo (prefira sempre os Excel)

### Instalação das dependências (Windows)
```powershell
winget install Python.Python.3.12
winget install wkhtmltopdf.wkhtmltox
winget install oschwartz10612.Poppler   # opcional
python -m pip install markdown
```
(macOS: `brew install python wkhtmltopdf poppler && pip3 install markdown` · Linux: use o gerenciador
de pacotes da distro + `pip install markdown`.)

## Instalar a skill no Claude Code
Clone este repositório para dentro da pasta de skills do seu Claude Code:
```bash
git clone https://github.com/kiofera/analista-de-investimentos.git ~/.claude/skills/analisar-carteira
```
Reinicie o Claude Code. A skill fica disponível como `/analisar-carteira`.

## Como usar
1. Crie uma pasta por cliente e coloque nela os relatórios da carteira (Kinvo em Excel tem leitura
   automática; planilhas de outras fontes e PDFs também são processados).
   **Exporte sempre a POSIÇÃO em Excel** (Kinvo: Carteira → Resumo de produtos → Exportar) além do
   extrato — o extrato e o PDF não trazem a posição atual, e o parser avisa se ela estiver velha.
2. Rode `/analisar-carteira` apontando para a pasta do cliente.
3. A skill gera o relatório (`.md` + `.pdf`) e o snapshot na pasta, a linha de base de fundamentos em
   `_fundamentos/`, e registra as recomendações em `decisoes.md` para conferir a execução na próxima.

Arquivos por cliente (fora deste repositório): `mandato-<cliente>.md`, `decisoes.md`, `precos.csv`
(opcional), `carteira-snapshot-*.md/.csv`, `relatorio-*.md/.pdf`. Templates em `templates/`.

Parser direto (sem o Claude Code):
```bash
python scripts/parse_carteira.py "<pasta-do-cliente>" [--no-snapshot]
python scripts/md_to_pdf.py "<pasta-do-cliente>/relatorio-AAAA-MM-DD.md"
```

## Atualizar para a versão mais nova
```bash
cd ~/.claude/skills/analisar-carteira && git pull
```

## Contribuir
Sugestões e melhorias são bem-vindas — abra uma issue (há templates para **novo layout de corretora**,
**bug** e **melhoria de doutrina**) ou um pull request. A doutrina de investimento
(`estrategia-investimento.md`) é o coração das recomendações; ajuste-a conforme a sua visão.

## Desenvolvimento
Testes (carteira sintética, sem dados reais; só stdlib):
```bash
python tests/test_parser.py
```
O CI (GitHub Actions) roda esses testes a cada push/PR na `main` — se quebrar o parser, o commit acusa.
Ao adicionar um layout novo em `detectar_tipo()`, inclua um caso sintético no teste.

## Privacidade
Este repositório **não contém dados de clientes**. As carteiras, o histórico de fundamentos
(`_fundamentos/`) e os relatórios ficam fora da skill, nas pastas de cada cliente — e nunca devem ser
versionados aqui (ver `.gitignore`).

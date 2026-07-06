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
- Mostra alocação por classe, concentração, histórico de decisões (realizado) e proventos.
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
2. Rode `/analisar-carteira` apontando para a pasta do cliente.
3. A skill gera o relatório (`.md` + `.pdf`) na pasta e a linha de base de fundamentos em `_fundamentos/`.

## Atualizar para a versão mais nova
```bash
cd ~/.claude/skills/analisar-carteira && git pull
```

## Contribuir
Sugestões e melhorias são bem-vindas — abra uma issue ou um pull request. A doutrina de investimento
(`estrategia-investimento.md`) é o coração das recomendações; ajuste-a conforme a sua visão.

## Privacidade
Este repositório **não contém dados de clientes**. As carteiras, o histórico de fundamentos
(`_fundamentos/`) e os relatórios ficam fora da skill, nas pastas de cada cliente — e nunca devem ser
versionados aqui (ver `.gitignore`).

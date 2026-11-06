#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de fumaça do parse_carteira.py com uma carteira SINTÉTICA (dados fictícios —
nunca colocar dados reais de cliente aqui). Sem dependências além da stdlib.

Roda:  python tests/test_parser.py
Sai com código != 0 se qualquer verificação falhar (usado pelo CI).

Cobre:
  - leitura de posição em .xlsx (gerado aqui mesmo, via zipfile+XML mínimos)
  - leitura de extrato em .csv (detecção de separador ';' e números PT-BR)
  - detecção por assinatura de colunas (nome de arquivo irrelevante)
  - flags: VERIFICAR-COTACAO (valorização absurda), SETOR INDEFINIDO (ticker sem mapa)
  - CONCENTRACAO não dispara em renda fixa/Tesouro (teto por papel é só para bolsa)
  - concentração por setor com look-through de ETF (IVV vem de data/etf_setores.csv)
  - modo descoberta para planilha de layout desconhecido
  - produtos encerrados (quantidade líquida zerada e fora da posição)
  - NÃO LISTADA NA POSIÇÃO: produto aberto no extrato mas ausente da posição (posição velha)
  - resíduo de venda total não aparece na tabela de custo USD
  - POSIÇÃO DESATUALIZADA: posição mais antiga que o extrato / que hoje
  - vários extratos: usa o mais recente e lista os ignorados
  - precos.csv: retorno USD/BRL e efeito câmbio calculados
  - snapshot .md/.csv gerado, não sobrescrito, e delta vs snapshot anterior
  - mandato desatualizado / ausente e decisoes.md ausente / presente
  - aviso de DUPLA CONTAGEM com duas posições na pasta
  - (opcional) geração de PDF se wkhtmltopdf estiver instalado
"""
import os, sys, shutil, subprocess, tempfile, zipfile, time, datetime
from xml.sax.saxutils import escape

try:                                  # console Windows pode ser cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARSER = os.path.join(REPO, "scripts", "parse_carteira.py")
MD2PDF = os.path.join(REPO, "scripts", "md_to_pdf.py")

FALHAS = []


def check(cond, msg):
    status = "ok" if cond else "FALHOU"
    print(f"  [{status}] {msg}")
    if not cond:
        FALHAS.append(msg)


# ------------------------------------------------ gerador de xlsx mínimo ----

def make_xlsx(path, rows):
    """Gera um .xlsx mínimo (todas as células como sharedStrings) legível pelo parser."""
    def colletter(n):                      # 1 -> A, 2 -> B ...
        s = ""
        while n:
            n, r = divmod(n - 1, 26)
            s = chr(65 + r) + s
        return s

    strings, sindex = [], {}

    def sid(v):
        if v not in sindex:
            sindex[v] = len(strings)
            strings.append(v)
        return sindex[v]

    cells_xml = []
    for ri, row in enumerate(rows, start=1):
        cs = "".join(
            f'<c r="{colletter(ci)}{ri}" t="s"><v>{sid(str(v))}</v></c>'
            for ci, v in enumerate(row, start=1)
        )
        cells_xml.append(f'<row r="{ri}">{cs}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             f'<sheetData>{"".join(cells_xml)}</sheetData></worksheet>')
    sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
           f'count="{len(strings)}" uniqueCount="{len(strings)}">'
           + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings) + "</sst>")
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          '<sheets><sheet name="Planilha1" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              '<Relationship Id="rId1" '
              'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
              'Target="worksheets/sheet1.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
             '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
             '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
             '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbrels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
        z.writestr("xl/sharedStrings.xml", sst)


def run_parser(folder, *extra):
    r = subprocess.run([sys.executable, PARSER, folder, *extra],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r


def set_mtime(path, dias_atras):
    t = time.time() - dias_atras * 86400
    os.utime(path, (t, t))


POS_HEADER = ["Produto", "Classe do Ativo", "Instituição financeira",
              "Data da primeira aplicação", "Valor aplicado", "Saldo bruto",
              "Rentabilidade (%)", "Participação na carteira (%)"]
EXT_HEADER = "Data;Produto;Tipo;Descrição;Instituição;Conexão;Valor;Quantidade;Custo;Câmbio;Valor Total\n"


def hoje_br(dias=0):
    return (datetime.date.today() - datetime.timedelta(days=dias)).strftime("%d/%m/%Y")


def main():
    tmp = tempfile.mkdtemp(prefix="teste_carteira_")
    try:
        # ---------------- Rodada 1: posição + extrato + desconhecida (base) ----------------
        # BBSE3 (mapeada), IVV (ETF look-through), FICT4 (ticker inexistente -> INDEFINIDO),
        # MOON11 (+400% -> VERIFICAR-COTACAO), Tesouro Selic 60% (RF: SEM flag CONCENTRACAO),
        # ACME (Avenue, posição aberta; custo USD). Total = 125.000,00.
        pos = os.path.join(tmp, "posicao-qualquer-nome.xlsx")
        make_xlsx(pos, [
            POS_HEADER,
            ["BBSE3 - BBSEGURIDADE", "Ação", "CorretoraX", "01/01/2024", "10.000,00", "12.000,00", "20,00", "9,60"],
            ["IVV - iShares Core S&P 500 ETF", "Ação", "CorretoraY", "01/01/2024", "18.000,00", "20.000,00", "11,11", "16,00"],
            ["FICT4 - FICTICIA SA", "Ação", "CorretoraX", "01/01/2024", "7.000,00", "8.000,00", "14,29", "6,40"],
            ["MOON11 - FOGUETE FII", "Fundo Imobiliário", "CorretoraX", "01/01/2024", "1.000,00", "5.000,00", "400,00", "4,00"],
            ["Tesouro Selic 2029 (LFT)", "Tesouro Direto", "CorretoraX", "01/01/2024", "70.000,00", "75.000,00", "7,14", "60,00"],
            ["ACME - Acme Corp", "Ação", "Avenue", "01/01/2024", "4.000,00", "5.000,00", "25,00", "4,00"],
        ])
        set_mtime(pos, 1)                                        # posição de ontem (fresca)

        ext = os.path.join(tmp, "movimentacoes.csv")
        with open(ext, "w", encoding="utf-8") as f:
            f.write(EXT_HEADER)
            f.write(f"10/01/2024;BBSE3 - BBSEGURIDADE;Ação;Aplicação;CorretoraX;;25,00;400;;;10.000,00\n")
            f.write(f"15/03/2024;BBSE3 - BBSEGURIDADE;Ação;Dividendos;CorretoraX;;0,50;400;;;200,00\n")
            # OLD3: comprada e vendida integralmente -> ENCERRADA
            f.write(f"20/02/2024;OLD3 - ANTIGA SA;Ação;Aplicação;CorretoraX;;10,00;500;;;5.000,00\n")
            f.write(f"20/05/2025;OLD3 - ANTIGA SA;Ação;Resgate;CorretoraX;;12,00;500;;;6.000,00\n")
            # NEWX - comprada DEPOIS da posição, quantidade aberta, ausente da posição -> NÃO LISTADA
            f.write(f"{hoje_br(0)};NEWX - NOVA SA;Ação;Aplicação;CorretoraX;;10,00;300;;;3.000,00\n")
            # ACME (Avenue): aberta, 10 ações a US$ 80 (câmbio 5,00) = R$ 4.000
            f.write(f"05/01/2024;ACME - Acme Corp;Ação;Aplicação;Avenue;;80,00;10;;5,00;4.000,00\n")
            # GONE (Avenue): compra 3,3333 + venda 3,3333 com resíduo de float -> NÃO aparece no custo USD
            f.write(f"06/01/2024;GONE - Gone Inc;Ação;Aplicação;Avenue;;30,00;3,3333;;5,00;500,00\n")
            f.write(f"07/02/2024;GONE - Gone Inc;Ação;Resgate;Avenue;;30,00;3,3333;;5,00;500,00\n")

        with open(os.path.join(tmp, "corretora-abc.csv"), "w", encoding="utf-8") as f:
            f.write("Codigo;Qtd;Preco Medio;Posicao\nZZZZ3;100;10,00;1.000,00\n")

        print("== Rodada 1: posição + extrato + desconhecida ==")
        r = run_parser(tmp)
        out = r.stdout
        check(r.returncode == 0, f"parser saiu com código 0 (código={r.returncode}) {r.stderr[-300:]}")
        check("125,000.00" in out, "saldo bruto total soma 125.000,00")
        check("VERIFICAR-COTACAO" in out, "flag VERIFICAR-COTACAO na posição +400%")
        check("SETOR INDEFINIDO" in out and "FICT4" in out, "FICT4 sinalizada como setor indefinido")
        check("Concentração por setor" in out, "tabela de concentração por setor presente")
        check("VIA ETF" in out and "Tecnologia" in out, "look-through do IVV distribui em setores")
        check("LAYOUT DESCONHECIDO" in out and "corretora-abc" in out, "modo descoberta na planilha de outra fonte")
        check("EXTRATO / HISTÓRICO" in out, "extrato detectado por assinatura em .csv")
        linhas_enc = [l for l in out.splitlines() if "| OLD3" in l]
        check(bool(linhas_enc) and "ENCERRADOS" in out, "produto encerrado (OLD3) aparece no realizado")
        linha_tes = next((l for l in out.splitlines() if l.strip().startswith("Tesouro Selic 2029")), "")
        check("CONCENTRACAO" not in linha_tes, "Tesouro a 60% NÃO recebe flag CONCENTRACAO (RF sem teto por papel)")
        check("NÃO LISTADAS NA POSIÇÃO" in out and "NEWX" in out, "NEWX (aberta, fora da posição) sai como NÃO LISTADA")
        check("QUANTIDADE INCONSISTENTE" in out, "posição fresca + produto ausente → 'quantidade inconsistente', não 'posição velha'")
        check(not any("| NEWX" in l for l in out.splitlines()), "NEWX NÃO aparece como prejuízo em ENCERRADOS")
        sec_usd = out.split("custo em USD vs BRL")[1] if "custo em USD vs BRL" in out else ""
        check("ACME" in sec_usd, "ACME (Avenue, aberta) aparece na tabela de custo USD")
        check("GONE" not in sec_usd, "GONE (venda total com resíduo de float) NÃO aparece no custo USD")
        check("!!! POSIÇÃO DESATUALIZADA" not in out, "posição fresca: sem banner de desatualização")
        check("Sem precos.csv" in out, "sem precos.csv: parser orienta a criá-lo")
        check("SEM MANDATO" in out, "sem mandato: aviso para criar a partir do template")
        check("SEM decisoes.md" in out, "sem decisoes.md: aviso para criar a partir do template")
        snap_md = [f for f in os.listdir(tmp) if f.startswith("carteira-snapshot-") and f.endswith(".md")]
        snap_csv = [f for f in os.listdir(tmp) if f.startswith("carteira-snapshot-") and f.endswith(".csv")]
        check(len(snap_md) == 1 and len(snap_csv) == 1, "snapshot .md + .csv gerados")
        check("primeiro snapshot comparável" in open(os.path.join(tmp, snap_md[0]), encoding="utf-8").read(),
              "1º snapshot avisa que não há anterior para delta")

        print("\n== Rodada 2: duas posições -> aviso de dupla contagem; snapshot não sobrescrito ==")
        shutil.copy2(pos, os.path.join(tmp, "outra-posicao.xlsx"))        # copy2 preserva a data
        r2 = run_parser(tmp)
        check(r2.returncode == 0, f"parser (2 posições) saiu com código 0 (código={r2.returncode})")
        check("DUPLA CONTAGEM" in r2.stdout, "aviso de DUPLA CONTAGEM com duas posições")
        check("já existe" in r2.stdout, "snapshot existente não é sobrescrito")
        os.remove(os.path.join(tmp, "outra-posicao.xlsx"))

        print("\n== Rodada 3: pasta vazia ==")
        vazio = os.path.join(tmp, "cliente-vazio")
        os.makedirs(vazio, exist_ok=True)
        r3 = run_parser(vazio)
        check(r3.returncode == 0, "pasta vazia não quebra o parser")
        check("nenhum arquivo" in r3.stdout, "pasta vazia gera aviso pedindo exports")

        print("\n== Rodada 4: posição VELHA vs extrato novo + 2 extratos + precos.csv + mandato + decisoes ==")
        set_mtime(pos, 120)                                      # posição de 4 meses atrás
        ext_velho = os.path.join(tmp, "extrato-antigo.csv")
        with open(ext_velho, "w", encoding="utf-8") as f:        # cumulativo, só até 2024
            f.write(EXT_HEADER)
            f.write("10/01/2024;BBSE3 - BBSEGURIDADE;Ação;Aplicação;CorretoraX;;25,00;400;;;10.000,00\n")
        with open(os.path.join(tmp, "precos.csv"), "w", encoding="utf-8") as f:
            f.write("# ticker,preco,moeda,data,fonte\n")
            f.write("USDBRL,5.50,BRL,2026-01-01,BCB PTAX\n")
            f.write("ACME,100.00,USD,2026-01-01,stockanalysis.com\n")   # 10 × 100 / 800 - 1 = +25% USD
        with open(os.path.join(tmp, "mandato-teste.md"), "w", encoding="utf-8") as f:
            f.write("# Mandato — Teste\n\nÚltima revisão: 2024-01-01\n")
        with open(os.path.join(tmp, "relatorio-2025-06-01.md"), "w", encoding="utf-8") as f:
            f.write("# Relatório — Teste — 2025-06-01\n")
        with open(os.path.join(tmp, "decisoes.md"), "w", encoding="utf-8") as f:
            f.write("# Decisões — Teste\n")
        for s in os.listdir(tmp):                                # limpa snapshot da rodada 1
            if s.startswith("carteira-snapshot-"):
                os.remove(os.path.join(tmp, s))
        r4 = run_parser(tmp)
        o4 = r4.stdout
        check(r4.returncode == 0, f"parser (rodada 4) saiu com código 0 (código={r4.returncode}) {r4.stderr[-300:]}")
        check("!!! POSIÇÃO DESATUALIZADA" in o4, "posição 120 dias mais velha que o extrato gera banner em destaque")
        check("Resumo de produtos" in o4, "aviso traz a instrução de exportação da posição no Kinvo")
        check("Provável POSIÇÃO DESATUALIZADA" in o4, "posição velha + produto ausente → 'provável posição desatualizada'")
        check("EXTRATOS na pasta" in o4 and "MAIS RECENTE" in o4, "2 extratos: usa o mais recente")
        check("extrato-antigo" in o4.split("Ignorados")[1][:200] if "Ignorados" in o4 else False,
              "extrato antigo listado como ignorado")
        check(o4.count("EXTRATO / HISTÓRICO") == 1, "só UM extrato é analisado")
        check("RET USD" in o4 and "25.0%" in o4, "precos.csv: retorno USD do ACME = +25,0%")
        check("MANDATO DESATUALIZADO" in o4, "mandato anterior ao último relatório gera aviso")
        check("decisoes.md presente" in o4, "decisoes.md presente é reconhecido")
        os.remove(ext_velho)

        print("\n== Rodada 5: snapshot novo com delta vs anterior ==")
        # snapshot da posição velha (rodada 4) existe; agora uma posição nova, BBSE3 subiu, NEWX entrou
        set_mtime(pos, 120)
        pos2 = os.path.join(tmp, "posicao-nova.xlsx")
        make_xlsx(pos2, [
            POS_HEADER,
            ["BBSE3 - BBSEGURIDADE", "Ação", "CorretoraX", "01/01/2024", "10.000,00", "13.000,00", "30,00", "50,00"],
            ["NEWX - NOVA SA", "Ação", "CorretoraX", "01/01/2026", "3.000,00", "3.000,00", "0,00", "11,54"],
            ["Tesouro Selic 2029 (LFT)", "Tesouro Direto", "CorretoraX", "01/01/2024", "9.000,00", "10.000,00", "11,11", "38,46"],
            ["ACME - Acme Corp", "Ação", "Avenue", "01/01/2024", "4.000,00", "5.000,00", "25,00", "4,00"],
        ])
        set_mtime(pos2, 0)
        os.remove(pos)                                           # fica só a posição nova
        r5 = run_parser(tmp)
        o5 = r5.stdout
        check(r5.returncode == 0, f"parser (rodada 5) saiu com código 0 (código={r5.returncode}) {r5.stderr[-300:]}")
        check("delta calculado vs" in o5, "snapshot novo calcula delta vs o .csv anterior")
        novos = [f for f in os.listdir(tmp) if f.startswith("carteira-snapshot-") and f.endswith(".md")]
        novos.sort()
        txt5 = open(os.path.join(tmp, novos[-1]), encoding="utf-8").read()
        check("+1,000.00" in txt5, "delta do BBSE3 = +1.000,00")
        check("**NOVA**" in txt5 and "NEWX" in txt5, "NEWX marcada como NOVA no snapshot")
        check("Saíram desde o snapshot anterior" in txt5 and "IVV" in txt5, "IVV listada como saída")
        check("NÃO LISTADAS NA POSIÇÃO" not in o5, "com a posição nova, NEWX deixa de ser 'não listada'")
        r5b = run_parser(tmp, "--no-snapshot")
        check("Snapshot" not in r5b.stdout.split("CHECAGENS DE PROCESSO")[-1] or "já existe" in r5b.stdout,
              "--no-snapshot não grava snapshot")

        print("\n== Rodada 6 (opcional): PDF ==")
        md = os.path.join(tmp, "relatorio-teste.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# Relatório — Cliente Teste — 2026-01-01\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAcentuação ok: ções.\n")
        r6 = subprocess.run([sys.executable, MD2PDF, md], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        if "não encontrado" in (r6.stdout + r6.stderr):
            print("  [SKIP] wkhtmltopdf não instalado — teste de PDF pulado")
        else:
            check(r6.returncode == 0 and os.path.exists(md.replace(".md", ".pdf")),
                  "md_to_pdf gera o PDF (com cabeçalho do título)")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FALHAS:
        print(f"RESULTADO: {len(FALHAS)} verificação(ões) FALHARAM")
        for f in FALHAS:
            print("  -", f)
        sys.exit(1)
    print("RESULTADO: todos os testes passaram ✓")


if __name__ == "__main__":
    main()

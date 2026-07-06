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
  - concentração por setor com look-through de ETF (IVV vem de data/etf_setores.csv)
  - modo descoberta para planilha de layout desconhecido
  - produtos encerrados (aplicado>0 e fora da posição)
  - aviso de DUPLA CONTAGEM com duas posições na pasta
  - (opcional) geração de PDF se wkhtmltopdf estiver instalado
"""
import os, sys, shutil, subprocess, tempfile, zipfile
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


def run_parser(folder):
    r = subprocess.run([sys.executable, PARSER, folder],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r


def main():
    tmp = tempfile.mkdtemp(prefix="teste_carteira_")
    try:
        # --- POSIÇÃO sintética (.xlsx; assinatura Kinvo: produto+classe+saldo) ---
        # BBSE3 (mapeada), IVV (ETF look-through), FICT4 (ticker inexistente -> INDEFINIDO),
        # MOON11 (+400% -> VERIFICAR-COTACAO). Total = 45.000,00.
        make_xlsx(os.path.join(tmp, "posicao-qualquer-nome.xlsx"), [
            ["Produto", "Classe do Ativo", "Instituição financeira",
             "Data da primeira aplicação", "Valor aplicado", "Saldo bruto",
             "Rentabilidade (%)", "Participação na carteira (%)"],
            ["BBSE3 - BBSEGURIDADE", "Ação", "CorretoraX", "01/01/2024",
             "10.000,00", "12.000,00", "20,00", "26,67"],
            ["IVV - iShares Core S&P 500 ETF", "Ação", "CorretoraY", "01/01/2024",
             "18.000,00", "20.000,00", "11,11", "44,44"],
            ["FICT4 - FICTICIA SA", "Ação", "CorretoraX", "01/01/2024",
             "7.000,00", "8.000,00", "14,29", "17,78"],
            ["MOON11 - FOGUETE FII", "Fundo Imobiliário", "CorretoraX", "01/01/2024",
             "1.000,00", "5.000,00", "400,00", "11,11"],
        ])

        # --- EXTRATO sintético (.csv ';'; assinatura: produto+descrição+valor total) ---
        with open(os.path.join(tmp, "movimentacoes.csv"), "w", encoding="utf-8") as f:
            f.write("Data;Produto;Tipo;Descrição;Instituição;Conexão;Valor;Quantidade;Custo;Câmbio;Valor Total\n")
            f.write("10/01/2024;BBSE3 - BBSEGURIDADE;Ação;Aplicação;CorretoraX;;25,00;400;;;10.000,00\n")
            f.write("15/03/2024;BBSE3 - BBSEGURIDADE;Ação;Dividendos;CorretoraX;;0,50;400;;;200,00\n")
            f.write("20/02/2024;OLD3 - ANTIGA SA;Ação;Aplicação;CorretoraX;;10,00;500;;;5.000,00\n")
            f.write("20/05/2025;OLD3 - ANTIGA SA;Ação;Resgate;CorretoraX;;12,00;500;;;6.000,00\n")

        # --- planilha de outra fonte (layout desconhecido -> modo descoberta) ---
        with open(os.path.join(tmp, "corretora-abc.csv"), "w", encoding="utf-8") as f:
            f.write("Codigo;Qtd;Preco Medio;Posicao\nZZZZ3;100;10,00;1.000,00\n")

        print("== Rodada 1: posição + extrato + desconhecida ==")
        r = run_parser(tmp)
        out = r.stdout
        check(r.returncode == 0, f"parser saiu com código 0 (código={r.returncode})")
        check("45,000.00" in out, "saldo bruto total soma 45.000,00")
        check("VERIFICAR-COTACAO" in out, "flag VERIFICAR-COTACAO na posição +400%")
        check("SETOR INDEFINIDO" in out and "FICT4" in out, "FICT4 sinalizada como setor indefinido")
        check("Concentração por setor" in out, "tabela de concentração por setor presente")
        check("VIA ETF" in out and "Tecnologia" in out, "look-through do IVV distribui em setores")
        check("LAYOUT DESCONHECIDO" in out and "corretora-abc" in out, "modo descoberta na planilha de outra fonte")
        check("EXTRATO / HISTÓRICO" in out, "extrato detectado por assinatura em .csv")
        check("OLD3" in out and "ENCERRADOS" in out, "produto encerrado (OLD3) aparece no realizado")
        check("MOON11" not in [l for l in out.splitlines() if "ENCERRADOS" in l], "seção encerrados não confunde posição atual")

        print("\n== Rodada 2: duas posições -> aviso de dupla contagem ==")
        shutil.copyfile(os.path.join(tmp, "posicao-qualquer-nome.xlsx"),
                        os.path.join(tmp, "outra-posicao.xlsx"))
        r2 = run_parser(tmp)
        check(r2.returncode == 0, f"parser (2 posições) saiu com código 0 (código={r2.returncode})")
        check("DUPLA CONTAGEM" in r2.stdout, "aviso de DUPLA CONTAGEM com duas posições")

        print("\n== Rodada 3: pasta vazia ==")
        vazio = os.path.join(tmp, "cliente-vazio")
        os.makedirs(vazio, exist_ok=True)
        r3 = run_parser(vazio)
        check(r3.returncode == 0, "pasta vazia não quebra o parser")
        check("nenhum arquivo" in r3.stdout, "pasta vazia gera aviso pedindo exports")

        print("\n== Rodada 4 (opcional): PDF ==")
        md = os.path.join(tmp, "relatorio-teste.md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("# Teste\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAcentuação ok: ções.\n")
        r4 = subprocess.run([sys.executable, MD2PDF, md], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
        if "não encontrado" in (r4.stdout + r4.stderr):
            print("  [SKIP] wkhtmltopdf não instalado — teste de PDF pulado")
        else:
            check(r4.returncode == 0 and os.path.exists(md.replace(".md", ".pdf")),
                  "md_to_pdf gera o PDF")
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

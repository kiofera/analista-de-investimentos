#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lê os relatórios de carteira de uma pasta de cliente — QUALQUER arquivo de dados, não só Kinvo —
e imprime um resumo estruturado. Usa apenas a biblioteca padrão.

Uso:
    python parse_carteira.py "<pasta-do-cliente>"

Como funciona (ingestão em 3 camadas):
  1. INVENTÁRIO — lista todos os arquivos de dados da pasta (.xlsx/.xls/.csv/.pdf).
  2. DETECÇÃO POR ASSINATURA — reconhece layouts conhecidos pelas COLUNAS (não pelo nome do arquivo):
       - posição Kinvo  (produto + classe + saldo)      -> análise completa de posição + setores
       - extrato Kinvo  (produto + descrição + total)   -> histórico, proventos, encerrados, câmbio
  3. MODO DESCOBERTA — planilha de layout desconhecido (B3, corretora, planilha própria...):
     imprime abas, cabeçalhos e amostra de linhas para o ANALISTA interpretar. Nunca adivinha
     o que cada coluna significa (regra anti-invenção). Layout recorrente? Adicionar uma
     assinatura em detectar_tipo() para virar leitura automática.
  PDFs são inventariados com a instrução de extração (pdftotext; se for imagem, pdftoppm/Poppler).

Lições embutidas (ver SKILL.md):
  - "Valor Total" da Avenue JÁ está em BRL; a coluna Câmbio é só referência. NÃO multiplicar.
  - A coluna "Rentabilidade (%)" do Kinvo é BUGADA em vários papéis -> calcular saldo/aplicado-1.
  - Posições com valorização absurda (>+300%) são SINALIZADAS p/ verificação com cotação ao vivo.
  - Duas posições de fontes diferentes na mesma pasta -> risco de DUPLA CONTAGEM (avisado).

Concentração por setor (doutrina v2, look-through de ETFs):
  - Mapa ticker->setor em  data/setores.csv   (editável; sem linha = INDEFINIDO, nunca chutar).
  - Composição de ETFs em  data/etf_setores.csv (pesos SEMPRE com fonte+data; sem linhas =
    look-through PENDENTE, reportado explicitamente).
"""
import sys, os, glob, re, zipfile, collections
import xml.etree.ElementTree as ET

try:                                  # saída consistente em UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def num(s):
    """Converte número PT-BR ('1.327.960,27') ou ASCII ('1327960.27') para float."""
    if s is None:
        return 0.0
    s = str(s).strip().replace("\xa0", "")
    if s == "":
        return 0.0
    if "," in s:                      # formato PT-BR
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


# ------------------------------------------------------------- leitura ------

def _sheet_rows(z, sheet_file, ss):
    sh = ET.fromstring(z.read(sheet_file))

    def colnum(ref):
        letters = "".join(c for c in ref if c.isalpha())
        n = 0
        for c in letters:
            n = n * 26 + (ord(c) - 64)
        return n

    rows = []
    sd = sh.find(NS + "sheetData")
    if sd is None:
        return rows
    for row in sd.findall(NS + "row"):
        cells, maxc = {}, 0
        for c in row.findall(NS + "c"):
            v = c.find(NS + "v")
            val = ""
            if v is not None:
                val = ss[int(v.text)] if c.get("t") == "s" else v.text
            ci = colnum(c.get("r"))
            maxc = max(maxc, ci)
            cells[ci] = val
        rows.append([cells.get(i, "") for i in range(1, maxc + 1)])
    return rows


def read_xlsx(path):
    """Retorna dict {nome_da_aba: linhas} com TODAS as abas do arquivo."""
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(NS + "si"):
            ss.append("".join(t.text or "" for t in si.iter(NS + "t")))

    def keynum(n):                     # sheet.xml, sheet1.xml, sheet10.xml -> ordena certo
        m = re.search(r"(\d+)", os.path.basename(n))
        return int(m.group(1)) if m else 0

    sheet_files = sorted((n for n in z.namelist()
                          if n.startswith("xl/worksheets/") and n.endswith(".xml")), key=keynum)
    names = []
    try:                               # nomes reais das abas (ordem do workbook)
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        names = [s.get("name") for s in wb.iter(NS + "sheet")]
    except Exception:
        pass
    out = {}
    for i, sf in enumerate(sheet_files):
        nome = names[i] if i < len(names) else f"aba{i + 1}"
        out[nome] = _sheet_rows(z, sf, ss)
    return out


def read_csv_file(path):
    """Lê CSV com detecção de encoding (utf-8/latin-1) e separador (;, , ou tab)."""
    import csv as _csv
    raw = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(path, encoding=enc) as f:
                raw = f.read()
            break
        except UnicodeDecodeError:
            continue
    if raw is None:
        return {}
    head = raw[:2048]
    sep = ";" if head.count(";") > head.count(",") else ","
    if head.count("\t") > max(head.count(";"), head.count(",")):
        sep = "\t"
    rows = list(_csv.reader(raw.splitlines(), delimiter=sep))
    return {"csv": rows}


def colmap(header):
    """Mapeia nome-normalizado -> índice de coluna."""
    def norm(s):
        return (s or "").lower().strip()
    return {norm(h): i for i, h in enumerate(header)}


def find_col(cmap, *needles):
    for key, i in cmap.items():
        if all(n in key for n in needles):
            return i
    return None


def first_col(cmap, options):
    """Primeira coluna existente entre as opções. (Não usar `or` — índice 0 é falsy!)"""
    for o in options:
        i = find_col(cmap, o)
        if i is not None:
            return i
    return None


def detectar_tipo(rows):
    """Identifica o layout pela ASSINATURA das colunas do cabeçalho (linha 1)."""
    if not rows or not rows[0]:
        return None
    cm = colmap(rows[0])
    tem = lambda *n: find_col(cm, *n) is not None
    if tem("produto") and tem("classe") and tem("saldo"):
        return "posicao-kinvo"
    if tem("produto") and tem("descri") and (tem("valor total") or tem("quantidade")):
        return "extrato-kinvo"
    return None


# ---------------------------------------------------------------- setores ----

def _data_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def _ler_csv_simples(nome):
    """Lê CSV em data/ ignorando comentários (#) e linhas vazias. None se não existir."""
    path = os.path.join(_data_dir(), nome)
    if not os.path.exists(path):
        return None
    import csv as _csv
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(next(_csv.reader([s])))
    return out


def _ticker(produto):
    p = (produto or "").strip()
    return (p.split(" - ")[0] if " - " in p else p).strip().upper()


def _setor_de(produto, smap):
    tk = _ticker(produto)
    if tk in smap:
        return smap[tk]
    pu = (produto or "").upper()
    for k, v in smap.items():             # chaves longas casam por substring (ex.: TESOURO SELIC)
        if len(k) >= 6 and k in pu:
            return v
    return None


def analisar_setores(holds, total):
    """holds = [(produto, saldo)]. Imprime concentração por setor com look-through de ETFs."""
    rows_s = _ler_csv_simples("setores.csv")
    if rows_s is None:
        print("\nAVISO: data/setores.csv não encontrado — análise setorial pulada.")
        return
    smap = {r[0].strip().upper(): r[1].strip() for r in rows_s if len(r) >= 2}
    emap = collections.defaultdict(list)
    for r in (_ler_csv_simples("etf_setores.csv") or []):
        if len(r) >= 3:
            emap[r[0].strip().upper()].append((r[1].strip(), num(r[2])))

    direto = collections.defaultdict(float)
    via_etf = collections.defaultdict(float)
    pendentes, indefinidos = [], []
    for prod, sal in holds:
        tk = _ticker(prod)
        setor = _setor_de(prod, smap)
        if tk in emap:                                    # ETF com composição mapeada
            soma = sum(p for _, p in emap[tk])
            for s, p in emap[tk]:
                via_etf[s] += sal * p / 100.0
            if soma < 99.0:                               # resto não mapeado fica explícito
                via_etf["(ETF: fatia não mapeada)"] += sal * (100.0 - soma) / 100.0
        elif setor == "ETF (look-through)":               # ETF sem composição -> pendente
            pendentes.append((prod, sal))
        elif setor is None:
            indefinidos.append((prod, sal))
        else:
            direto[setor] += sal

    print("\n--- Concentração por setor (com look-through de ETFs) ---")
    print("    Teto da doutrina: ~25–30% por setor econômico (renda fixa/previdência têm regra própria)")
    print(f"    {'SETOR':28s} {'DIRETO':>13s} {'VIA ETF':>11s} {'TOTAL':>13s} {'% CART':>7s}  FLAG")
    setores = sorted(set(direto) | set(via_etf),
                     key=lambda s: -(direto.get(s, 0) + via_etf.get(s, 0)))
    sem_teto = ("Renda fixa", "Previdência (renda fixa)")
    for s in setores:
        d, v = direto.get(s, 0.0), via_etf.get(s, 0.0)
        t = d + v
        pct = t / total * 100 if total else 0.0
        flag = "ALERTA-SETOR" if pct > 25 and s not in sem_teto else ""
        print(f"    {s[:28]:28s} {d:13,.0f} {v:11,.0f} {t:13,.0f} {pct:6.2f}%  {flag}")
    for prod, sal in pendentes:
        print(f"    >>> LOOK-THROUGH PENDENTE: {prod[:40]} (R$ {sal:,.0f}) — preencher "
              f"data/etf_setores.csv com fonte+data antes de concluir a leitura setorial.")
    for prod, sal in indefinidos:
        print(f"    >>> SETOR INDEFINIDO: {prod[:40]} (R$ {sal:,.0f}) — mapear em data/setores.csv.")


# ---------------------------------------------------------------- análises ---

def analisar_posicao(rows, label):
    cm = colmap(rows[0])
    ci_prod = find_col(cm, "produto")
    ci_classe = find_col(cm, "classe")
    ci_apl = find_col(cm, "aplicado")
    ci_sal = find_col(cm, "saldo")
    data = rows[1:]
    hold = [r for r in data if ci_sal is not None and num(r[ci_sal]) > 0]
    total = sum(num(r[ci_sal]) for r in hold)

    print("=" * 70)
    print("POSIÇÃO ATUAL (fonte autoritativa):", label)
    print("=" * 70)
    print(f"Posições com saldo > 0: {len(hold)}")
    print(f"SALDO BRUTO TOTAL:      R$ {total:,.2f}")
    print(f"Aplicado (custo atual): R$ {sum(num(r[ci_apl]) for r in hold):,.2f}")

    print("\n--- Alocação por classe ---")
    cl = collections.defaultdict(float)
    for r in hold:
        cl[r[ci_classe]] += num(r[ci_sal])
    for k, v in sorted(cl.items(), key=lambda x: -x[1]):
        print(f"  {v:14,.2f}  {v/total*100:5.2f}%  {k}")

    print("\n--- Posições (ordenadas por saldo) ---")
    print(f"  {'PRODUTO':38s} {'APLICADO':>12s} {'SALDO':>12s} {'VALORIZ':>8s} {'PESO':>6s}  FLAG")
    flags = []
    for r in sorted(hold, key=lambda x: -num(x[ci_sal])):
        apl, sal = num(r[ci_apl]), num(r[ci_sal])
        val = (sal / apl - 1) * 100 if apl else 0.0
        peso = sal / total * 100
        flag = ""
        if abs(val) >= 300:
            flag += "VERIFICAR-COTACAO "
        if peso >= 5:
            flag += "CONCENTRACAO "
        if val <= -25:
            flag += "PERDA "
        if flag:
            flags.append((r[ci_prod], val, peso, flag.strip()))
        print(f"  {r[ci_prod][:38]:38s} {apl:12,.0f} {sal:12,.0f} {val:7.0f}% {peso:5.2f}%  {flag}")

    if flags:
        print("\n  >>> SINALIZADOS para atenção/verificação:")
        for prod, val, peso, flag in flags:
            print(f"      [{flag}] {prod[:50]} (valoriz {val:.0f}%, peso {peso:.1f}%)")

    analisar_setores([(r[ci_prod], num(r[ci_sal])) for r in hold], total)

    current = set(r[ci_prod] for r in hold)
    return total, current


def analisar_extrato(rows, label, current=None):
    current = current or set()
    cm = colmap(rows[0])
    ci_data = find_col(cm, "data")
    ci_prod = find_col(cm, "produto")
    ci_desc = find_col(cm, "descri")
    ci_tot = first_col(cm, ["valor total", "total"])
    ci_inst = find_col(cm, "institui")
    ci_qtd = find_col(cm, "quantidade")
    ci_camb = first_col(cm, ["câmbio", "cambio"])
    data = rows[1:]

    print("\n" + "=" * 70)
    print("EXTRATO / HISTÓRICO:", label)
    print("=" * 70)
    datas = [r[ci_data] for r in data if r[ci_data]]
    print(f"Transações: {len(data)} | Período: {datas[-1]} a {datas[0]}")

    print("\n--- Atividade (compras/resgates) por ano ---")
    neg = collections.Counter(r[ci_data][-4:] for r in data
                              if any(x in r[ci_desc].lower() for x in ("aplica", "resgate")))
    for y in sorted(neg):
        print(f"  {y}: {neg[y]}")

    # Proventos por tipo (Avenue já em BRL; NÃO multiplicar por câmbio)
    prov = collections.defaultdict(float)
    for r in data:
        d = r[ci_desc]
        if d in ("Dividendos", "Juros sobre capital", "Rendimentos"):
            prov[d] += num(r[ci_tot])
    print("\n--- Proventos recebidos (BRL) ---")
    for k, v in prov.items():
        print(f"  {k:22s} R$ {v:,.2f}")

    # Proventos por ano — acompanha a evolução da renda (papel da carteira BR)
    prov_ano = collections.defaultdict(float)
    for r in data:
        if r[ci_desc] in ("Dividendos", "Juros sobre capital", "Rendimentos") and r[ci_data]:
            prov_ano[r[ci_data][-4:]] += num(r[ci_tot])
    print("\n--- Proventos por ano (renda gerada) ---")
    for y in sorted(prov_ano):
        print(f"  {y}: R$ {prov_ano[y]:,.2f}")

    # Resultado realizado de produtos encerrados
    agg = collections.defaultdict(lambda: {"apl": 0.0, "res": 0.0, "prov": 0.0})
    for r in data:
        a = agg[r[ci_prod]]
        d, v = r[ci_desc], num(r[ci_tot])
        if d.startswith("Aplica"):
            a["apl"] += v
        elif d == "Resgate":
            a["res"] += v
        elif d in ("Dividendos", "Juros sobre capital", "Rendimentos"):
            a["prov"] += v
    print("\n--- Resultado realizado de produtos ENCERRADOS (res+prov-apl) ---")
    print("    (encerrado = NÃO está na posição atual; usa a posição oficial como verdade)")
    enc = []
    for p, a in agg.items():
        if a["apl"] > 0 and p not in current:
            enc.append((a["res"] + a["prov"] - a["apl"], p, a))
    for res, p, a in sorted(enc):
        print(f"  {res:>11,.0f} | apl {a['apl']:>10,.0f} res {a['res']:>10,.0f} prov {a['prov']:>7,.0f} | {p[:40]}")

    # Custo em USD vs BRL para posições da Avenue (base p/ reportar retorno em 2 moedas)
    if ci_inst is not None and ci_camb is not None and ci_qtd is not None:
        fx = collections.defaultdict(lambda: {"brl": 0.0, "usd": 0.0, "qtd": 0.0})
        for r in data:
            inst = (r[ci_inst] or "").upper()
            if inst not in ("AVENUE", "PASSFOLIO"):
                continue
            d = r[ci_desc]
            brl, cb, q = num(r[ci_tot]), num(r[ci_camb]), num(r[ci_qtd])
            if not cb:
                continue
            f = fx[r[ci_prod]]
            if d.startswith("Aplica"):
                f["brl"] += brl; f["usd"] += brl / cb; f["qtd"] += q
            elif d == "Resgate":
                f["brl"] -= brl; f["usd"] -= brl / cb; f["qtd"] -= q
        cur = [(p, f) for p, f in fx.items() if p in current and f["usd"] > 1]
        if cur:
            print("\n--- Posições EUA (Avenue): custo em USD vs BRL ---")
            print("    Retorno BRL = saldo(posição)/custoBRL-1 ; Retorno USD = (qtd×preçoUSD ao vivo)/custoUSD-1")
            print("    Efeito câmbio = Retorno BRL − Retorno USD. Buscar preço USD e USD/BRL ao vivo p/ completar.")
            print(f"    {'PRODUTO':40s} {'QTD':>10s} {'CUSTO USD':>12s} {'CUSTO BRL':>12s} {'FX médio':>9s}")
            for p, f in sorted(cur, key=lambda x: -x[1]["usd"]):
                fxm = f["brl"] / f["usd"] if f["usd"] else 0
                print(f"    {p[:40]:40s} {f['qtd']:10.4f} {f['usd']:12,.2f} {f['brl']:12,.2f} {fxm:9.3f}")


def modo_descoberta(rows, label):
    """Layout desconhecido: expõe estrutura e amostra para o analista interpretar (não adivinha)."""
    print("\n" + "=" * 70)
    print("LAYOUT DESCONHECIDO (modo descoberta):", label)
    print("=" * 70)
    n_dados = max(0, len(rows) - 1)
    print(f"Linhas: {len(rows)} (1 cabeçalho? + {n_dados})")
    amostra = rows[:7]
    for i, r in enumerate(amostra):
        cells = " | ".join((c or "")[:18] for c in r[:10])
        rotulo = "CABEÇALHO?" if i == 0 else f"linha {i}"
        print(f"  [{rotulo:10s}] {cells}")
    if len(rows) > 7:
        print(f"  ... (+{len(rows) - 7} linhas)")
    print("  >>> ANALISTA: interprete as colunas acima antes de usar os números (anti-invenção).")
    print("      Se este layout for recorrente, adicione uma assinatura em detectar_tipo().")


def main():
    if len(sys.argv) < 2:
        print("Uso: python parse_carteira.py \"<pasta-do-cliente>\"")
        sys.exit(1)
    folder = sys.argv[1]

    arquivos = sorted(
        f for f in glob.glob(os.path.join(folder, "*"))
        if os.path.splitext(f)[1].lower() in (".xlsx", ".xls", ".csv", ".pdf")
    )
    print("=" * 70)
    print("INVENTÁRIO DE ARQUIVOS DE DADOS:", folder)
    print("=" * 70)
    if not arquivos:
        print("  (nenhum arquivo .xlsx/.xls/.csv/.pdf na pasta — peça os exports ao usuário)")
        return
    for f in arquivos:
        print(f"  {os.path.getsize(f):>10,} bytes  {os.path.basename(f)}")
    print()

    posicoes, extratos, desconhecidos, pdfs = [], [], [], []
    for f in arquivos:
        ext = os.path.splitext(f)[1].lower()
        base = os.path.basename(f)
        if ext == ".pdf":
            pdfs.append(f)
            continue
        if ext == ".xls":
            desconhecidos.append((None, f"{base} (formato .xls antigo — converter para .xlsx/.csv)"))
            continue
        try:
            abas = read_xlsx(f) if ext == ".xlsx" else read_csv_file(f)
        except Exception as e:
            desconhecidos.append((None, f"{base} (erro ao ler: {e})"))
            continue
        multi = len(abas) > 1
        for nome, rows in abas.items():
            if not rows:
                continue
            label = f"{base}" + (f" [aba: {nome}]" if multi else "")
            tipo = detectar_tipo(rows)
            if tipo == "posicao-kinvo":
                posicoes.append((rows, label))
            elif tipo == "extrato-kinvo":
                extratos.append((rows, label))
            else:
                desconhecidos.append((rows, label))

    current = set()
    for rows, label in posicoes:
        _total, cur = analisar_posicao(rows, label)
        current |= cur
    if len(posicoes) > 1:
        print("\n>>> ATENÇÃO: MAIS DE UMA POSIÇÃO na pasta — risco de DUPLA CONTAGEM se as fontes "
              "se sobrepõem (mesmo ativo em dois relatórios). Reconciliar antes de somar totais.")
    for rows, label in extratos:
        analisar_extrato(rows, label, current)
    for rows, label in desconhecidos:
        if rows is None:
            print(f"\nAVISO: {label}")
        else:
            modo_descoberta(rows, label)
    if pdfs:
        print("\n" + "=" * 70)
        print("PDFs ENCONTRADOS (extrair antes de usar):")
        print("=" * 70)
        for p in pdfs:
            print(f"  {os.path.basename(p)}")
        print("  >>> 1º tente texto:  pdftotext -layout \"<arquivo>\" saida.txt")
        print("  >>> se vier vazio (PDF-imagem, ex.: Kinvo): renderizar com Poppler "
              "(pdftoppm -png -r 200) e ler as imagens.")

    if not posicoes:
        print("\nAVISO: nenhuma POSIÇÃO reconhecida automaticamente. Se houver planilha em modo "
              "descoberta acima, interprete-a; senão, peça o export de posição ao usuário.")
    if posicoes:
        print("\nLEMBRETE: confira se o SALDO BRUTO TOTAL bate com o relatório/topo da fonte; "
              "VERIFIQUE com cotação ao vivo qualquer posição marcada VERIFICAR-COTACAO; e "
              "resolva pendências de setor (INDEFINIDO / look-through PENDENTE) antes de "
              "concluir a leitura de concentração setorial.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lê os relatórios de carteira de uma pasta de cliente — QUALQUER arquivo de dados, não só Kinvo —
e imprime um resumo estruturado. Usa apenas a biblioteca padrão.

Uso:
    python parse_carteira.py "<pasta-do-cliente>" [--no-snapshot]

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

Checagens de consistência (adicionadas em 2026-11 após auditoria com dados reais):
  - POSIÇÃO DESATUALIZADA: a posição (fonte autoritativa) é comparada com a data mais recente do
    extrato e com a data de hoje. Posição velha gera aviso em destaque + instrução de exportação.
  - Vários EXTRATOS na pasta: usa o mais recente (maior data final) e lista os ignorados.
  - "ENCERRADO" só quando a quantidade líquida no extrato zerou. Produto com quantidade líquida
    positiva mas ausente da posição sai como "NÃO LISTADA NA POSIÇÃO" (sinal de posição velha),
    nunca como prejuízo realizado.
  - Resíduos de venda total (quantidade ~0 por arredondamento) não aparecem na tabela de custo USD.
  - Flag CONCENTRACAO (teto por papel) não dispara em renda fixa/previdência/caixa.
  - MANDATO: avisa se o mandato é mais antigo que o último relatório ou se não existe.
  - DECISÕES: avisa se não existe decisoes.md (registro de recomendação vs. execução).

Arquivos opcionais na pasta do cliente:
  - precos.csv  (ticker,preco,moeda,data,fonte; linha USDBRL obrigatória para câmbio) — com ele o
    parser calcula retorno em USD, em BRL e o efeito câmbio das posições em dólar. Preços vêm do
    analista COM fonte+data (anti-invenção preservada).

Saída gerada (a menos de --no-snapshot):
  - carteira-snapshot-AAAA-MM-DD.md + .csv (data = data do arquivo de posição). Nunca sobrescreve
    um snapshot existente. Com um .csv anterior na pasta, imprime o delta por posição.

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
import sys, os, glob, re, zipfile, collections, datetime
import xml.etree.ElementTree as ET

try:                                  # saída consistente em UTF-8
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PROVENTOS = ("Dividendos", "Juros sobre capital", "Rendimentos")
EPS_QTD = 1e-3                        # quantidade abaixo disto = posição zerada (resíduo de float)
DIAS_POSICAO_VS_EXTRATO = 7           # extrato mais novo que a posição em mais que isto -> aviso
DIAS_POSICAO_VELHA = 30               # posição com mais que isto de idade -> aviso
CLASSES_SEM_TETO_PAPEL = ("previd", "tesouro", "renda fixa", "caixa", "poupan", "cdb", "lci", "lca")


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


def data_br(s):
    """'dd/mm/aaaa' (ou 'aaaa-mm-dd') -> date; None se não reconhecer."""
    s = (s or "").strip()[:10]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fmt_data(d):
    return d.strftime("%d/%m/%Y") if d else "?"


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


def _ler_csv_simples(path):
    """Lê CSV ignorando comentários (#) e linhas vazias. None se não existir."""
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
    for sep in (" - ", " — "):
        if sep in p:
            return p.split(sep)[0].strip().upper()
    return p.upper()


def _setor_de(produto, smap):
    tk = _ticker(produto)
    if tk in smap:
        return smap[tk]
    pu = (produto or "").upper()
    for k, v in smap.items():             # chaves longas casam por substring (ex.: TESOURO SELIC)
        if len(k) >= 6 and k in pu:
            return v
    return None


def _classe_sem_teto(classe):
    """Classes em que o teto por papel do mandato não se aplica (caixa/RF/previdência)."""
    c = (classe or "").lower()
    if "imobili" in c:                    # FII é bolsa, tem teto
        return False
    if c.strip() == "fundo":              # fundo DI/RF (Kinvo chama só de "Fundo")
        return True
    return any(k in c for k in CLASSES_SEM_TETO_PAPEL)


def analisar_setores(holds, total):
    """holds = [(produto, saldo)]. Imprime concentração por setor com look-through de ETFs."""
    rows_s = _ler_csv_simples(os.path.join(_data_dir(), "setores.csv"))
    if rows_s is None:
        print("\nAVISO: data/setores.csv não encontrado — análise setorial pulada.")
        return
    smap = {r[0].strip().upper(): r[1].strip() for r in rows_s if len(r) >= 2}
    emap = collections.defaultdict(list)
    for r in (_ler_csv_simples(os.path.join(_data_dir(), "etf_setores.csv")) or []):
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
    sem_teto = ("Renda fixa", "Previdência (renda fixa)", "Renda fixa (USD)")
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
    """Imprime a análise da posição. Retorna dict com total, current (set), holds (lista)."""
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
        if peso >= 5 and not _classe_sem_teto(r[ci_classe]):
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
    print("  (teto por papel não se aplica a caixa/renda fixa/previdência — regra própria no mandato)")

    holds = [(r[ci_prod], r[ci_classe], num(r[ci_apl]), num(r[ci_sal])) for r in hold]
    analisar_setores([(p, s) for p, _, _, s in holds], total)
    return {"total": total, "current": set(p for p, _, _, _ in holds), "holds": holds}


def extrato_periodo(rows):
    """(data_min, data_max) do extrato, lendo a coluna Data."""
    cm = colmap(rows[0])
    ci_data = find_col(cm, "data")
    if ci_data is None:
        return None, None
    ds = [data_br(r[ci_data]) for r in rows[1:] if len(r) > ci_data]
    ds = [d for d in ds if d]
    return (min(ds), max(ds)) if ds else (None, None)


def analisar_extrato(rows, label, current=None, saldos=None, precos=None):
    current = current or set()
    saldos = saldos or {}
    precos = precos or {}
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
    dmin, dmax = extrato_periodo(rows)
    print(f"Transações: {len(data)} | Período: {fmt_data(dmin)} a {fmt_data(dmax)}")

    print("\n--- Atividade (compras/resgates) por ano ---")
    neg = collections.Counter(r[ci_data][-4:] for r in data
                              if any(x in r[ci_desc].lower() for x in ("aplica", "resgate")))
    for y in sorted(neg):
        print(f"  {y}: {neg[y]}")

    # Proventos por tipo (Avenue já em BRL; NÃO multiplicar por câmbio)
    prov = collections.defaultdict(float)
    for r in data:
        d = r[ci_desc]
        if d in PROVENTOS:
            prov[d] += num(r[ci_tot])
    print("\n--- Proventos recebidos (BRL) ---")
    for k, v in prov.items():
        print(f"  {k:22s} R$ {v:,.2f}")

    prov_ano = collections.defaultdict(float)
    for r in data:
        if r[ci_desc] in PROVENTOS and r[ci_data]:
            prov_ano[r[ci_data][-4:]] += num(r[ci_tot])
    print("\n--- Proventos por ano (renda gerada) ---")
    for y in sorted(prov_ano):
        print(f"  {y}: R$ {prov_ano[y]:,.2f}")

    # Agregado por produto: aplicado/resgatado/proventos + QUANTIDADE LÍQUIDA (decide "encerrado")
    agg = collections.defaultdict(lambda: {"apl": 0.0, "res": 0.0, "prov": 0.0,
                                           "qtd": 0.0, "tem_qtd": False})
    for r in data:
        a = agg[r[ci_prod]]
        d, v = r[ci_desc], num(r[ci_tot])
        q = num(r[ci_qtd]) if ci_qtd is not None else 0.0
        if d.startswith("Aplica"):
            a["apl"] += v; a["qtd"] += q
        elif d == "Resgate":
            a["res"] += v; a["qtd"] -= q
        elif d in PROVENTOS:
            a["prov"] += v
        if q:
            a["tem_qtd"] = True

    enc, nao_listadas = [], []
    for p, a in agg.items():
        if a["apl"] <= 0 or p in current:
            continue
        aberta = (a["qtd"] > EPS_QTD) if a["tem_qtd"] else (a["res"] == 0)
        (nao_listadas if aberta else enc).append((a["res"] + a["prov"] - a["apl"], p, a))

    print("\n--- Resultado realizado de produtos ENCERRADOS (res+prov-apl) ---")
    print("    (encerrado = quantidade líquida zerada no extrato E fora da posição atual)")
    for res, p, a in sorted(enc):
        print(f"  {res:>11,.0f} | apl {a['apl']:>10,.0f} res {a['res']:>10,.0f} prov {a['prov']:>7,.0f} | {p[:40]}")
    if nao_listadas:
        print("\n  >>> NÃO LISTADAS NA POSIÇÃO (quantidade líquida > 0 no extrato, mas ausentes da posição):")
        print("      Provável POSIÇÃO DESATUALIZADA — exporte a posição atual antes de concluir. "
              "NÃO são prejuízo realizado.")
        for _res, p, a in sorted(nao_listadas, key=lambda x: -x[2]["apl"]):
            q = f"qtd {a['qtd']:,.4f}" if a["tem_qtd"] else "qtd indisponível"
            print(f"      {p[:44]:44s} apl {a['apl']:>10,.0f} res {a['res']:>8,.0f}  {q}")

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
        # posição aberta = quantidade líquida > 0 (resíduo de venda total fica de fora)
        cur = [(p, f) for p, f in fx.items() if f["qtd"] > EPS_QTD and f["usd"] > 1]
        if cur:
            usdbrl = precos.get("USDBRL")
            com_preco = bool(usdbrl)
            print("\n--- Posições EUA (Avenue): custo em USD vs BRL ---")
            print("    Retorno BRL = saldo(posição)/custoBRL-1 ; Retorno USD = (qtd×preçoUSD)/custoUSD-1")
            print("    Efeito câmbio = Retorno BRL − Retorno USD.")
            if com_preco:
                print(f"    Preços de precos.csv (USD/BRL {usdbrl['preco']:.4f}, {usdbrl['fonte']}, "
                      f"{usdbrl['data']}). Posição sem preço = 'indisponível'.")
            else:
                print("    Sem precos.csv na pasta: preencha (ticker,preco,moeda,data,fonte + linha USDBRL)"
                      " para o parser calcular os retornos; até lá, buscar preço USD e câmbio ao vivo.")
            cab = f"    {'PRODUTO':40s} {'QTD':>10s} {'CUSTO USD':>12s} {'CUSTO BRL':>12s} {'FX médio':>9s}"
            if com_preco:
                cab += f" {'RET USD':>9s} {'RET BRL':>9s} {'CÂMBIO':>8s}"
            print(cab)
            for p, f in sorted(cur, key=lambda x: -x[1]["usd"]):
                fxm = f["brl"] / f["usd"] if f["usd"] else 0
                linha = f"    {p[:40]:40s} {f['qtd']:10.4f} {f['usd']:12,.2f} {f['brl']:12,.2f} {fxm:9.3f}"
                if com_preco:
                    pr = precos.get(_ticker(p))
                    sal = saldos.get(p)
                    if pr and sal:
                        ret_usd = f["qtd"] * pr["preco"] / f["usd"] - 1
                        ret_brl = sal / f["brl"] - 1
                        linha += (f" {ret_usd*100:8.1f}% {ret_brl*100:8.1f}% "
                                  f"{(ret_brl-ret_usd)*100:+7.1f}pp")
                    elif pr and not sal:
                        linha += "  (sem saldo na posição: indisponível)"
                    else:
                        linha += "  (sem preço em precos.csv: indisponível)"
                print(linha)
            if com_preco:
                faltam = [_ticker(p) for p, _ in cur if _ticker(p) not in precos]
                if faltam:
                    print(f"    >>> sem preço em precos.csv: {', '.join(sorted(set(faltam)))}")


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


# --------------------------------------------------------- precos.csv --------

def ler_precos(folder):
    """precos.csv (ticker,preco,moeda,data,fonte). Retorna {TICKER: {...}} ou {} se ausente."""
    rows = _ler_csv_simples(os.path.join(folder, "precos.csv"))
    if not rows:
        return {}
    out = {}
    for r in rows:
        if len(r) < 2 or r[0].strip().lower() == "ticker":
            continue
        tk = r[0].strip().upper()
        out[tk] = {"preco": num(r[1]),
                   "moeda": (r[2].strip() if len(r) > 2 else ""),
                   "data": (r[3].strip() if len(r) > 3 else "?"),
                   "fonte": (r[4].strip() if len(r) > 4 else "sem fonte")}
    sem_fonte = [t for t, v in out.items() if v["fonte"] in ("", "sem fonte")]
    if sem_fonte:
        print(f"\nAVISO precos.csv: sem fonte para {', '.join(sem_fonte)} — regra anti-invenção: "
              "todo preço com fonte+data.")
    if "USDBRL" not in out:
        print("\nAVISO precos.csv: falta a linha USDBRL (câmbio) — retornos em 2 moedas não calculados.")
    return out


# ------------------------------------------------------- checagens de processo

def checar_consistencia_datas(pos_path, extrato_max, hoje):
    """Posição (mtime) vs. data final do extrato vs. hoje. Avisa em destaque se a posição é velha."""
    if not pos_path:
        return
    dpos = datetime.date.fromtimestamp(os.path.getmtime(pos_path))
    avisos = []
    if extrato_max and (extrato_max - dpos).days > DIAS_POSICAO_VS_EXTRATO:
        avisos.append(f"o extrato vai até {fmt_data(extrato_max)}, mas o arquivo de posição é de "
                      f"{fmt_data(dpos)} ({(extrato_max - dpos).days} dias mais antigo)")
    if (hoje - dpos).days > DIAS_POSICAO_VELHA:
        avisos.append(f"o arquivo de posição tem {(hoje - dpos).days} dias (de {fmt_data(dpos)})")
    if avisos:
        print("\n" + "!" * 70)
        print("!!! POSIÇÃO DESATUALIZADA — os números de posição acima NÃO refletem a carteira atual:")
        for a in avisos:
            print(f"!!!   - {a}")
        print("!!! Peça/exporte a POSIÇÃO atual no Kinvo: Carteira -> Resumo de produtos -> Exportar Excel")
        print("!!! (o extrato e o PDF-imagem NÃO substituem a posição em Excel).")
        print("!" * 70)
    return dpos


def _data_de_nome(nome):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", nome)
    return data_br(m.group(1)) if m else None


def checar_mandato_e_decisoes(folder):
    print("\n" + "=" * 70)
    print("CHECAGENS DE PROCESSO (mandato / decisões)")
    print("=" * 70)
    rels = sorted(d for d in (_data_de_nome(os.path.basename(f))
                              for f in glob.glob(os.path.join(folder, "relatorio-*.md"))) if d)
    ult_rel = rels[-1] if rels else None
    mands = glob.glob(os.path.join(folder, "mandato-*.md"))
    if not mands:
        print("  >>> SEM MANDATO (mandato-<cliente>.md): crie a partir de templates/mandato-template.md "
              "e confirme as regras com o gestor antes de recomendar.")
    else:
        m = mands[0]
        drev = None
        try:
            with open(m, encoding="utf-8") as f:
                txt = f.read()
            mm = re.search(r"ltima revis[aã]o:\s*(\d{4}-\d{2}-\d{2})", txt)
            drev = data_br(mm.group(1)) if mm else None
        except OSError:
            pass
        if drev is None:
            drev = datetime.date.fromtimestamp(os.path.getmtime(m))
        msg = f"  Mandato: {os.path.basename(m)} (última revisão {fmt_data(drev)})"
        if ult_rel:
            msg += f" | último relatório {fmt_data(ult_rel)}"
        print(msg)
        if ult_rel and drev < ult_rel:
            print("  >>> MANDATO DESATUALIZADO: é anterior ao último relatório. Registre as pendências que "
                  "os relatórios pediram (novos ativos/classes, teses, limites) e atualize 'Última revisão'.")
    dec = os.path.join(folder, "decisoes.md")
    if os.path.exists(dec):
        print(f"  Decisões: decisoes.md presente — ao gerar o relatório, atualize o status das "
              f"recomendações anteriores (seguida / ignorada / pendente) e abra as novas.")
    else:
        print("  >>> SEM decisoes.md: crie a partir de templates/decisoes-template.md para registrar "
              "recomendação vs. execução (é o que permite ao histórico 'aprender').")


# ------------------------------------------------------------- snapshot ------

def _snapshot_csv_anterior(folder, data_pos):
    cands = []
    for f in glob.glob(os.path.join(folder, "carteira-snapshot-*.csv")):
        d = _data_de_nome(os.path.basename(f))
        if d and d < data_pos:
            cands.append((d, f))
    return max(cands)[1] if cands else None


def gravar_snapshot(folder, pos, data_pos, pos_label):
    import csv as _csv
    base = os.path.join(folder, f"carteira-snapshot-{data_pos:%Y-%m-%d}")
    md_path, csv_path = base + ".md", base + ".csv"
    if os.path.exists(md_path) or os.path.exists(csv_path):
        print(f"\nSnapshot {os.path.basename(base)}.md/.csv já existe — não sobrescrevo "
              "(apague-o se quiser regenerar).")
        return
    holds = pos["holds"]
    total = pos["total"]
    apl_total = sum(a for _, _, a, _ in holds)

    anterior = {}
    ant_path = _snapshot_csv_anterior(folder, data_pos)
    if ant_path:
        with open(ant_path, encoding="utf-8-sig", newline="") as f:
            for r in _csv.DictReader(f):
                anterior[_ticker(r["produto"])] = (r["produto"], num(r["saldo"]))
    ant_total = sum(v for _, v in anterior.values()) if anterior else None

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["produto", "classe", "aplicado", "saldo"])
        for p, c, a, s in sorted(holds, key=lambda x: -x[3]):
            w.writerow([p, c, f"{a:.2f}", f"{s:.2f}"])

    linhas = []
    linhas.append(f"# Carteira — snapshot {data_pos:%Y-%m-%d} (gerado pelo parser)")
    linhas.append("")
    linhas.append(f"**Fonte:** {pos_label} (arquivo de posição datado de {fmt_data(data_pos)}).")
    linhas.append(f"**Saldo bruto:** R$ {total:,.2f} | **Aplicado:** R$ {apl_total:,.2f} | "
                  f"**Resultado:** R$ {total - apl_total:,.2f} "
                  f"({(total / apl_total - 1) * 100 if apl_total else 0:+.2f}%)")
    if ant_path:
        linhas.append(f"**vs snapshot anterior** ({os.path.basename(ant_path)}): patrimônio "
                      f"R$ {ant_total:,.2f} → R$ {total:,.2f} ({total - ant_total:+,.2f}; "
                      f"{(total / ant_total - 1) * 100 if ant_total else 0:+.2f}%).")
    else:
        linhas.append("**vs snapshot anterior:** nenhum `.csv` anterior na pasta — este é o primeiro "
                      "snapshot comparável; o delta aparece a partir do próximo.")
    linhas.append("")
    linhas.append("> Gerado automaticamente a partir da posição. Números com formato PT-BR nos arquivos "
                  "de origem; aqui em formato numérico. Conferir o total com o topo do relatório da fonte.")
    linhas.append("")
    linhas.append("## Alocação por classe")
    linhas.append("")
    linhas.append("| Classe | Valor | % |")
    linhas.append("|---|---|---|")
    cl = collections.defaultdict(float)
    for _, c, _, s in holds:
        cl[c] += s
    for c, v in sorted(cl.items(), key=lambda x: -x[1]):
        linhas.append(f"| {c} | {v:,.2f} | {v / total * 100:.2f}% |")
    linhas.append("")
    linhas.append("## Posições (ordenadas por saldo)")
    linhas.append("")
    cab = "| Ativo | Classe | Aplicado | Saldo | Valoriz. | Peso |"
    sep = "|---|---|---|---|---|---|"
    if ant_path:
        cab += " Δ vs anterior |"
        sep += "---|"
    linhas += [cab, sep]
    vistos = set()
    for p, c, a, s in sorted(holds, key=lambda x: -x[3]):
        val = (s / a - 1) * 100 if a else 0.0
        row = f"| {p} | {c} | {a:,.2f} | {s:,.2f} | {val:+.1f}% | {s / total * 100:.2f}% |"
        if ant_path:
            tk = _ticker(p)
            vistos.add(tk)
            if tk in anterior:
                d = s - anterior[tk][1]
                row += f" {d:+,.2f} |"
            else:
                row += " **NOVA** |"
        linhas.append(row)
    if ant_path:
        saidas = [anterior[tk][0] for tk in anterior if tk not in vistos]
        if saidas:
            linhas.append("")
            linhas.append("**Saíram desde o snapshot anterior:** " + "; ".join(saidas))
    linhas.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"\nSnapshot gravado: {os.path.basename(md_path)} (+ .csv para o próximo delta)"
          + (f"; delta calculado vs {os.path.basename(ant_path)}" if ant_path else ""))


# ------------------------------------------------------------------ main ------

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = set(a for a in sys.argv[1:] if a.startswith("--"))
    if not args:
        print("Uso: python parse_carteira.py \"<pasta-do-cliente>\" [--no-snapshot]")
        sys.exit(1)
    folder = args[0]
    hoje = datetime.date.today()

    arquivos = sorted(
        f for f in glob.glob(os.path.join(folder, "*"))
        if os.path.splitext(f)[1].lower() in (".xlsx", ".xls", ".csv", ".pdf")
        and os.path.basename(f).lower() not in ("precos.csv",)
        and not os.path.basename(f).lower().startswith("carteira-snapshot-")
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
                posicoes.append((rows, label, f))
            elif tipo == "extrato-kinvo":
                extratos.append((rows, label, f))
            else:
                desconhecidos.append((rows, label))

    # --- posições (mais de uma = dupla contagem; a mais recente manda no snapshot) ---
    posicoes.sort(key=lambda x: -os.path.getmtime(x[2]))
    current, saldos, pos_info, pos_path, pos_label = set(), {}, None, None, None
    for rows, label, path in posicoes:
        info = analisar_posicao(rows, label)
        current |= info["current"]
        for p, _, _, s in info["holds"]:
            saldos.setdefault(p, s)
        if pos_info is None:
            pos_info, pos_path, pos_label = info, path, label
    if len(posicoes) > 1:
        print("\n>>> ATENÇÃO: MAIS DE UMA POSIÇÃO na pasta — risco de DUPLA CONTAGEM se as fontes "
              "se sobrepõem (mesmo ativo em dois relatórios). Reconciliar antes de somar totais. "
              f"O snapshot usa a mais recente: {pos_label}.")

    # --- extratos: usar o mais recente; listar os ignorados ---
    extrato_max = None
    if extratos:
        com_data = [(extrato_periodo(rows)[1] or datetime.date.min, rows, label, path)
                    for rows, label, path in extratos]
        com_data.sort(key=lambda x: x[0], reverse=True)
        dmax, rows, label, path = com_data[0]
        extrato_max = dmax if dmax != datetime.date.min else None
        if len(com_data) > 1:
            print(f"\n>>> {len(com_data)} EXTRATOS na pasta — usando o MAIS RECENTE "
                  f"({label}, até {fmt_data(extrato_max)}). Ignorados (mais antigos/cumulativos): "
                  + "; ".join(f"{l} (até {fmt_data(d if d != datetime.date.min else None)})"
                              for d, _, l, _ in com_data[1:]))
        precos = ler_precos(folder)
        analisar_extrato(rows, label, current, saldos, precos)

    # --- consistência de datas (posição vs extrato vs hoje) ---
    data_pos = None
    if pos_path:
        data_pos = checar_consistencia_datas(pos_path, extrato_max, hoje)

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

    checar_mandato_e_decisoes(folder)

    if pos_info and "--no-snapshot" not in flags:
        gravar_snapshot(folder, pos_info, data_pos or hoje, pos_label)

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

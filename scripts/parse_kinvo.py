#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lê os exports do Kinvo (Excel) de uma pasta de cliente e imprime um resumo
estruturado e confiável da carteira. Usa apenas a biblioteca padrão (zipfile +
xml.etree) — um .xlsx é um zip de XML, não precisa de openpyxl/pandas.

Uso:
    python parse_kinvo.py "<pasta-do-cliente>"

Detecta automaticamente:
  - posição/resumo:  arquivo contendo "resumo" no nome  (FONTE AUTORITATIVA p/ valor atual)
  - extrato:         arquivo contendo "extrato" no nome  (histórico de movimentações)

Lições embutidas (ver SKILL.md):
  - "Valor Total" da Avenue JÁ está em BRL; a coluna Câmbio é só referência. NÃO multiplicar.
  - A coluna "Rentabilidade (%)" do Kinvo é BUGADA em vários papéis -> calcular saldo/aplicado-1.
  - Sanidade: posições com valorização absurda (>+300%) ou peso alto são SINALIZADAS para
    verificação de cotação ao vivo antes de reportar (caso Micron: dado correto, mas só dá pra
    saber checando a cotação real).
"""
import sys, os, glob, zipfile, collections
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


def read_xlsx(path):
    """Retorna lista de linhas (cada uma lista de strings) da 1ª planilha."""
    z = zipfile.ZipFile(path)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(NS + "si"):
            ss.append("".join(t.text or "" for t in si.iter(NS + "t")))
    sheet_name = sorted(n for n in z.namelist()
                        if n.startswith("xl/worksheets/") and n.endswith(".xml"))[0]
    sh = ET.fromstring(z.read(sheet_name))

    def colnum(ref):
        letters = "".join(c for c in ref if c.isalpha())
        n = 0
        for c in letters:
            n = n * 26 + (ord(c) - 64)
        return n

    rows = []
    for row in sh.find(NS + "sheetData").findall(NS + "row"):
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


def analisar_posicao(path):
    rows = read_xlsx(path)
    cm = colmap(rows[0])
    ci_prod = find_col(cm, "produto")
    ci_classe = find_col(cm, "classe")
    ci_apl = find_col(cm, "aplicado")
    ci_sal = find_col(cm, "saldo")
    ci_part = find_col(cm, "participa")
    data = rows[1:]
    hold = [r for r in data if ci_sal is not None and num(r[ci_sal]) > 0]
    total = sum(num(r[ci_sal]) for r in hold)

    print("=" * 70)
    print("POSIÇÃO ATUAL (fonte autoritativa):", os.path.basename(path))
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
    current = set(r[ci_prod] for r in hold)
    return total, current


def analisar_extrato(path, current=None):
    current = current or set()
    rows = read_xlsx(path)
    cm = colmap(rows[0])
    ci_data = find_col(cm, "data")
    ci_prod = find_col(cm, "produto")
    ci_desc = find_col(cm, "descri")
    ci_tot = find_col(cm, "valor total") or find_col(cm, "total")
    ci_inst = find_col(cm, "institui")
    ci_qtd = find_col(cm, "quantidade")
    ci_camb = find_col(cm, "câmbio") or find_col(cm, "cambio")
    data = rows[1:]

    print("\n" + "=" * 70)
    print("EXTRATO / HISTÓRICO:", os.path.basename(path))
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


def main():
    if len(sys.argv) < 2:
        print("Uso: python parse_kinvo.py \"<pasta-do-cliente>\"")
        sys.exit(1)
    folder = sys.argv[1]
    xlsx = glob.glob(os.path.join(folder, "*.xlsx"))
    pos = next((f for f in xlsx if "resumo" in os.path.basename(f).lower()
                or "posi" in os.path.basename(f).lower()), None)
    ext = next((f for f in xlsx if "extrato" in os.path.basename(f).lower()), None)

    current = set()
    if pos:
        _total, current = analisar_posicao(pos)
    else:
        print("AVISO: não achei o export de POSIÇÃO (nome com 'resumo'/'posicao'). "
              "Peça ao usuário o export de posição do Kinvo.")
    if ext:
        analisar_extrato(ext, current)
    else:
        print("\nAVISO: não achei o EXTRATO (nome com 'extrato').")
    if pos:
        print("\nLEMBRETE: confira se o SALDO BRUTO TOTAL bate com o relatório/topo do Kinvo, "
              "e VERIFIQUE com cotação ao vivo qualquer posição marcada VERIFICAR-COTACAO.")


if __name__ == "__main__":
    main()

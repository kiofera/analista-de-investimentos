#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converte um relatório Markdown em PDF (layout limpo, tabelas legíveis, A4).

Uso:
    python md_to_pdf.py "<arquivo.md>" ["<saida.pdf>"]
Se a saída for omitida, gera o PDF com o mesmo nome do .md.

Requisitos (já instalados nesta máquina):
    - Python lib: markdown      (pip install markdown)
    - wkhtmltopdf               (winget wkhtmltopdf.wkhtmltox) — renderiza HTML->PDF
"""
import sys, os, shutil, subprocess, tempfile

try:
    import markdown
except ImportError:
    print("ERRO: falta a lib 'markdown'. Rode: python -m pip install markdown")
    sys.exit(1)

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: 'Segoe UI', Calibri, Arial, sans-serif; font-size: 10.5pt;
       color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 19pt; color: #0b3d62; border-bottom: 2px solid #0b3d62;
     padding-bottom: 5px; margin: 0 0 12px; }
h2 { font-size: 13.5pt; color: #0b3d62; margin: 18px 0 7px;
     border-bottom: 1px solid #d0d7de; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #244; margin: 13px 0 5px; }
p { margin: 6px 0; }
table { border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9.3pt; }
th, td { border: 1px solid #c6ccd2; padding: 4px 7px; text-align: left;
         vertical-align: top; }
th { background: #0b3d62; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #f3f6f9; }
code { background: #eef1f4; padding: 1px 4px; border-radius: 3px;
       font-family: Consolas, monospace; font-size: 9pt; }
blockquote { border-left: 3px solid #9aa7b2; margin: 8px 0; padding: 3px 12px;
             color: #555; background: #f7f9fb; font-size: 9.6pt; }
strong { color: #0b3d62; }
ul, ol { margin: 6px 0 6px 18px; }
hr { border: none; border-top: 1px solid #d0d7de; margin: 14px 0; }
"""

HTML = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<style>{css}</style></head><body>{body}</body></html>"""


def find_wkhtmltopdf():
    for p in (r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
              r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe"):
        if os.path.exists(p):
            return p
    return shutil.which("wkhtmltopdf")


def main():
    if len(sys.argv) < 2:
        print('Uso: python md_to_pdf.py "<arquivo.md>" ["<saida.pdf>"]')
        sys.exit(1)
    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(md_path)[0] + ".pdf"

    with open(md_path, encoding="utf-8") as f:
        text = f.read()
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = HTML.format(css=CSS, body=body)

    wk = find_wkhtmltopdf()
    if not wk:
        print("ERRO: wkhtmltopdf não encontrado. Instale: winget install wkhtmltopdf.wkhtmltox")
        sys.exit(1)

    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8") as t:
        t.write(html)
        html_path = t.name
    try:
        r = subprocess.run([wk, "--encoding", "utf-8", "--enable-local-file-access",
                            "--footer-font-size", "7", "--footer-spacing", "4",
                            "--footer-right", "pág. [page]/[topage]",
                            "--quiet", html_path, pdf_path],
                           capture_output=True, text=True)
        if r.returncode != 0 and not os.path.exists(pdf_path):
            print("ERRO wkhtmltopdf:", r.stderr[-500:])
            sys.exit(1)
    finally:
        try: os.remove(html_path)
        except OSError: pass
    print("PDF gerado:", pdf_path)


if __name__ == "__main__":
    main()

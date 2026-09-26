"""INFORME.md + página de resultados -> Informe_RR_Topstep.pdf (Chromium headless).

Uso: python3 -m scripts.pdf [ruta_chrome]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

CHROME = sys.argv[1] if len(sys.argv) > 1 else "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
CSS = """
@page { size: A4 landscape; margin: 12mm; }
body { font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 9.5pt; color:#1a1a1a; line-height:1.4; }
h1 { font-size: 17pt; border-bottom: 2px solid #1f4e79; padding-bottom:4px; color:#1f4e79; }
h2 { font-size: 13pt; color:#1f4e79; margin-top:18px; border-bottom:1px solid #ccd; page-break-after: avoid; }
h3 { font-size: 11pt; color:#333; margin-top:14px; page-break-after: avoid; }
table { border-collapse: collapse; width:100%; margin:8px 0 12px; font-size:7.6pt; page-break-inside: avoid; }
th { background:#1f4e79; color:#fff; padding:3px 4px; text-align:left; }
td { border-bottom:1px solid #dde; padding:2.5px 4px; white-space:nowrap; }
tr:nth-child(even) td { background:#f4f6fa; }
code, pre { font-family: 'DejaVu Sans Mono', monospace; font-size:8pt; background:#f3f3f3; }
pre { padding:6px; white-space:pre-wrap; }
.hoja { page-break-before: always; page-break-after: always; }
h1.tr { font-size: 16pt; border: none; margin: 0 0 2px; }
.sub { color:#666; font-size:8pt; margin:0 0 8px; }
table.tr { font-size: 6.6pt; page-break-inside: auto; margin-top:4px; }
table.tr th { background:#1f3a5f; text-align:center; padding:4px 3px; }
table.tr td { text-align:center; padding:2px 3px; border-bottom:2px solid #fff; background:#f1f2f4; line-height:1.15; }
table.tr tr:nth-child(even) td { background:#f1f2f4; }
table.tr tr.baj td { background:#e2e3e6; }
table.tr tr.opt td { background:#dde9f6; }
table.tr tr.man td { background:#e9defa; }
table.tr td.id, table.tr td.b { font-weight:bold; }
table.tr td.am { background:#fde68a !important; }
table.tr td.ve { background:#bbf0cf !important; }
table.tr td.ro { background:#f8c8cc !important; }
.mini { font-size:5.6pt; color:#555; font-weight:normal; }
.notas { font-size:7pt; color:#444; margin-top:2px; }
"""


def main():
    md = Path("INFORME.md").read_text()
    corte = md.index("## 2. Método")
    pagina = Path("resultados/tabla_resultados.html").read_text()
    body = (markdown.markdown(md[:corte], extensions=["tables", "fenced_code"]) + pagina
            + markdown.markdown(md[corte:], extensions=["tables", "fenced_code"]))
    html = (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>Informe RR Topstep</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    subprocess.run([CHROME, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={Path('Informe_RR_Topstep.pdf').resolve()}", f.name],
                   check=True, capture_output=True)


if __name__ == "__main__":
    main()

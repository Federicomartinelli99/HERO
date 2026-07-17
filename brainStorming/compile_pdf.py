import os
import re
import subprocess
import sys

# Lista dei pacchetti richiesti
REQUIRED_PACKAGES = ["markdown", "xhtml2pdf"]

def check_and_install_dependencies():
    """Verifica se i pacchetti richiesti sono installati e, se necessario, li installa."""
    missing_packages = []
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg)
        except ImportError:
            missing_packages.append(pkg)
            
    if missing_packages:
        print(f"Pacchetti mancanti rilevati: {missing_packages}")
        print("Installazione in corso tramite pip...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
            print("Installazione completata con successo!\n")
        except Exception as e:
            print(f"Errore durante l'installazione dei pacchetti: {e}")
            print("Prova ad installarli manualmente eseguendo:")
            print(f"pip install {' '.join(REQUIRED_PACKAGES)}")
            sys.exit(1)

# Esegui il controllo dei pacchetti prima di procedere
check_and_install_dependencies()

import markdown
from xhtml2pdf import pisa

def clean_markdown_links(text):
    """
    Pulisce i link relativi ai file markdown (es. [Fase 1](fase_1.md) o [Tasks](fase_1_tasks.md))
    in modo che nel PDF finale appaiano come semplice testo in grassetto o senza l'estensione del file.
    """
    # Rimuove il link mantenendo solo il testo per i file .md locali
    cleaned = re.sub(r'\[([^\]]+)\]\((fase_[^)]+\.md)\)', r'**\1**', text)
    cleaned = re.sub(r'\[([^\]]+)\]\((README\.md)\)', r'**\1**', text)
    return cleaned

def compile_markdown_to_pdf():
    # Definisce la cartella di lavoro
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Sequenza ordinata di compilazione dei file
    files_order = [
        "README.md",
        "fase_1.md",
        "fase_1_tasks.md",
        "fase_2.md",
        "fase_2_tasks.md",
        "fase_3.md",
        "fase_3_tasks.md",
        "fase_4.md",
        "fase_4_tasks.md",
        "fase_5.md",
        "fase_5_tasks.md",
        "fase_6.md",
        "fase_6_tasks.md",
        "fase_7.md",
        "fase_7_tasks.md",
        "fase_8.md",
        "fase_8_tasks.md",
        "fase_9.md",
        "fase_9_tasks.md",
    ]
    
    merged_markdown = ""
    
    # Legge e concatena tutti i file
    for file_name in files_order:
        file_path = os.path.join(current_dir, file_name)
        if os.path.exists(file_path):
            print(f"Lettura di: {file_name}...")
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Pulisce i link interni
                content = clean_markdown_links(content)
                merged_markdown += content + "\n\n<div style='page-break-after: always;'></div>\n\n"
        else:
            print(f"Attenzione: {file_name} non trovato, saltato.")
            
    if not merged_markdown.strip():
        print("Errore: Nessun contenuto trovato da compilare!")
        return

    # Converte il Markdown in HTML (abilitando tabelle ed estensioni extra)
    print("Conversione Markdown in HTML...")
    html_content = markdown.markdown(merged_markdown, extensions=['extra', 'codehilite'])
    
    # CSS per la formattazione avanzata del PDF
    css_styles = """
    <style>
        @page {
            size: a4;
            margin: 2cm;
            @frame footer {
                -pdf-frame-content: footer_content;
                bottom: 1cm;
                left: 2cm;
                right: 2cm;
                height: 1cm;
            }
        }
        body {
            font-family: Helvetica, Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #333333;
        }
        h1 {
            font-size: 20pt;
            color: #1e3a8a;
            margin-top: 15pt;
            margin-bottom: 10pt;
            border-bottom: 1px solid #1e3a8a;
            padding-bottom: 5pt;
        }
        h2 {
            font-size: 15pt;
            color: #2563eb;
            margin-top: 15pt;
            margin-bottom: 8pt;
        }
        h3 {
            font-size: 12pt;
            color: #1d4ed8;
            margin-top: 10pt;
            margin-bottom: 6pt;
        }
        p {
            margin-bottom: 8pt;
            text-align: justify;
        }
        ul, ol {
            margin-left: 15pt;
            margin-bottom: 8pt;
        }
        li {
            margin-bottom: 4pt;
        }
        code {
            font-family: Courier, monospace;
            background-color: #f3f4f6;
            color: #dc2626;
            font-size: 9pt;
            padding: 1pt 3pt;
        }
        pre {
            font-family: Courier, monospace;
            background-color: #f3f4f6;
            padding: 8pt;
            border-left: 3px solid #cbd5e1;
            margin-bottom: 10pt;
            display: block;
            font-size: 9pt;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10pt;
            margin-bottom: 10pt;
            font-size: 9pt;
        }
        th {
            background-color: #1e3a8a;
            color: white;
            font-weight: bold;
            padding: 6pt;
            border: 1px solid #1e3a8a;
            text-align: left;
        }
        td {
            padding: 6pt;
            border: 1px solid #e2e8f0;
            text-align: left;
        }
        tr:nth-child(even) {
            background-color: #f8fafc;
        }
        blockquote {
            background-color: #eff6ff;
            border-left: 4px solid #3b82f6;
            padding: 5pt 10pt;
            margin-bottom: 10pt;
        }
        .footer-text {
            font-size: 8pt;
            color: #64748b;
            text-align: center;
        }
    </style>
    """
    
    # Struttura finale HTML
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        {css_styles}
    </head>
    <body>
        <div id="footer_content" class="footer-text">
            Progetto HERO - Specifica Roadmap di Sviluppo | Pagina <pdf:pagenumber> di <pdf:pagecount>
        </div>
        {html_content}
    </body>
    </html>
    """
    
    # File PDF di output
    output_pdf_path = os.path.join(current_dir, "roadmap_HERO.pdf")
    
    # Genera il PDF
    print(f"Generazione del file PDF: roadmap_HERO.pdf...")
    with open(output_pdf_path, "wb") as output_file:
        pisa_status = pisa.CreatePDF(
            src=full_html,
            dest=output_file
        )
        
    if not pisa_status.err:
        print(f"\nSuccesso! PDF compilato con successo all'indirizzo:")
        print(output_pdf_path)
    else:
        print(f"\nErrore durante la compilazione del PDF: {pisa_status.err}")

if __name__ == "__main__":
    compile_markdown_to_pdf()

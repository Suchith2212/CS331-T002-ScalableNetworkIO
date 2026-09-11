#!/usr/bin/env python3
import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

def convert_md_to_pdf(md_path, pdf_path):
    print(f"Converting {md_path} to {pdf_path}...")
    
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1a2a3a'),
        alignment=TA_CENTER,
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'DocH1',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#2c3e50'),
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#34495e'),
        spaceBefore=10,
        spaceAfter=6,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=6,
        alignment=TA_JUSTIFY
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor('#555555'),
        alignment=TA_CENTER,
        spaceAfter=15
    )

    code_style = ParagraphStyle(
        'DocCode',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#2c3e50'),
        backColor=colors.HexColor('#f8f9fa'),
        borderColor=colors.HexColor('#e9ecef'),
        borderWidth=1,
        borderPadding=6,
        spaceBefore=6,
        spaceAfter=6
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#2c3e50'),
        alignment=TA_CENTER
    )

    story = []

    lines = content.split('\n')
    i = 0
    in_table = False
    table_lines = []
    in_code = False
    code_lines = []

    while i < len(lines):
        line = lines[i]

        # Code block handling
        if line.strip().startswith('```'):
            if in_code:
                # End of code block
                code_text = "<br/>".join(code_lines).replace(" ", "&nbsp;")
                story.append(Paragraph(code_text, code_style))
                code_lines = []
                in_code = False
            else:
                in_code = True
                code_lines = []
            i += 1
            continue

        if in_code:
            code_lines.append(line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
            i += 1
            continue

        # Table handling
        if line.strip().startswith('|'):
            table_lines.append(line)
            in_table = True
            i += 1
            continue
        elif in_table:
            # End of table
            in_table = False
            story.append(build_table(table_lines, table_header_style, table_cell_style))
            table_lines = []

        # Headings
        if line.startswith('# '):
            story.append(Paragraph(format_text(line[2:]), title_style))
        elif line.startswith('## '):
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor('#cbd5e1'), spaceBefore=10, spaceAfter=8))
            story.append(Paragraph(format_text(line[3:]), h1_style))
        elif line.startswith('### '):
            story.append(Paragraph(format_text(line[4:]), h2_style))
        elif line.startswith('- ') or line.startswith('* '):
            item_text = f"• {format_text(line[2:])}"
            story.append(Paragraph(item_text, body_style))
        elif line.startswith('---'):
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceBefore=8, spaceAfter=8))
        elif line.strip() == '':
            i += 1
            continue
        else:
            if "Course:" in line or "Team ID:" in line or "Authors:" in line or "Target Environment:" in line:
                story.append(Paragraph(format_text(line), meta_style))
            else:
                story.append(Paragraph(format_text(line), body_style))

        i += 1

    if in_table and table_lines:
        story.append(build_table(table_lines, table_header_style, table_cell_style))

    doc.build(story)
    print(f"Successfully generated PDF: {pdf_path}")

def format_text(text):
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    # Bold **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Italic *text*
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    # Inline code `text`
    text = re.sub(r'`(.*?)`', r'<font face="Courier" color="#c7254e"><b>\1</b></font>', text)
    return text

def build_table(lines, header_style, cell_style):
    data = []
    for line in lines:
        if '---' in line:
            continue # skip header separator row
        cols = [c.strip() for c in line.strip('|').split('|')]
        data.append(cols)

    if not data:
        return Spacer(1, 1)

    table_data = []
    for r_idx, row in enumerate(data):
        row_data = []
        for col in row:
            style = header_style if r_idx == 0 else cell_style
            row_data.append(Paragraph(format_text(col), style))
        table_data.append(row_data)

    t = Table(table_data, hAlign='CENTER')
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
    ]))
    return t

if __name__ == '__main__':
    md_file = os.path.join("report", "final_report.md")
    pdf_file = os.path.join("report", "final_report.pdf")
    convert_md_to_pdf(md_file, pdf_file)

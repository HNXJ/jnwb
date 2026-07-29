---
name: docx-editing
description: |
  Reliable DOCX editing, layout stabilization, automated page break enforcement, table/figure pagination control, and template-driven document generation using python-docx and docxtpl.
---

# Reliable DOCX Editing & Layout Stabilization Protocol

## Core Principles & Technical Mechanics

Microsoft Word (`.docx`) files do not store fixed physical page positions. They use an OpenXML reflowable layout engine where page boundaries are calculated dynamically based on paragraph line heights, margins, font metrics, and image anchors.

Editing raw text or inserting content without explicit layout controls causes **downstream reflow**, moving figures, splitting table rows across pages, and detaching headings/captions.

---

## 4 Golden Rules for DOCX Stability

### 1. Hard Page Breaks (`<w:br w:type="page"/>`) & Section Breaks
- Always enforce explicit hard page breaks or `page_break_before = True` on major section titles (`Abstract`, `Introduction`, `Methods`, `Results`, `Discussion`, `Figures`, `References`).
- Prevents text edits in one section from pushing the next section heading to the bottom of an earlier page.

### 2. Strict Paragraph & Table Pagination Controls
- **`keep_with_next = True`**: Must be applied to all Headings and Figure Captions. Ensures a heading or caption is never orphaned at the bottom of a page without its preceding/following content.
- **`cant_split = True`**: Applied to Table Rows. Guarantees that multi-line table rows do not split awkwardly across page boundaries.
- **`keep_together = True`**: Ensures all lines of a specific block or figure caption remain on the same page.

### 3. Inline Figures vs. Floating Text Anchors
- **Floating images** (`Square`, `Tight`, `Behind Text`) anchor to paragraph character offsets. When preceding text length changes, anchor paragraphs move, causing floating images to jump pages unpredictably.
- **Inline images** act like block elements inside dedicated centered paragraphs with zero space-before/after, keeping figure images strictly linked with their captions.

### 4. Template-Based Generation (`docxtpl` / `python-docx-template`)
- Never perform naive regex string substitution on raw `.docx` XML or text runs. Word breaks single words across multiple `<w:r>` (run) nodes if spelling or tracking changes occurred.
- Use Jinja2 tags (e.g., `{{ intro_text }}`, `{{ figure_1_img }}`) in a designed baseline template (`template.docx`). `DocxTemplate` injects text, tables, and images while leaving document styles, headers, footers, and page breaks untouched.

---

## Automated Layout Locking Utility (`fix_docx_layout.py`)

Below is the canonical Python utility using `python-docx` to inspect and lock document pagination.

```python
import docx
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def lock_docx_layout(input_docx: str, output_docx: str, major_sections=None):
    """
    Applies hard pagination controls to a DOCX file:
    - Sets page_break_before on major section headings.
    - Sets keep_with_next on all Headings and Figure captions.
    - Prevents table rows from splitting across pages (w:cantSplit).
    """
    if major_sections is None:
        major_sections = ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References", "Figures"]
        
    doc = docx.Document(input_docx)
    
    # 1. Enforce heading & caption pagination
    for p in doc.paragraphs:
        text = p.text.strip()
        style_name = p.style.name if p.style else ""
        
        # Keep Headings & Captions attached to following element
        if "Heading" in style_name or text.startswith("Figure.") or text.startswith("Figure "):
            p.paragraph_format.keep_with_next = True
            
        # Hard Page Breaks before major section titles
        if any(text.startswith(sec) for sec in major_sections) and ("Heading" in style_name or text in major_sections):
            p.paragraph_format.page_break_before = True
            
    # 2. Prevent table row splitting
    for table in doc.tables:
        for row in table.rows:
            trPr = row._tr.get_or_add_trPr()
            trPr.append(OxmlElement('w:cantSplit'))

    doc.save(output_docx)
    print(f"Layout locked and saved to: {output_docx}")
```

---

## Non-Destructive Structural Audit (Zero Dependencies)

Before modifying any `.docx` file, audit its internal XML structure using Python's built-in `zipfile` and `xml.etree.ElementTree`:

```python
import zipfile
import xml.etree.ElementTree as ET

def audit_docx(path: str):
    with zipfile.ZipFile(path, 'r') as z:
        xml_content = z.read('word/document.xml')

    root = ET.fromstring(xml_content)
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

    paragraphs = root.findall('.//w:p', ns)
    page_breaks = [br for br in root.findall('.//w:br', ns) if br.attrib.get(f"{{{ns['w']}}}type") == 'page']
    drawings = root.findall('.//w:drawing', ns)
    tables = root.findall('.//w:tbl', ns)

    print(f"--- DOCX Audit Receipt ---")
    print(f"File: {path}")
    print(f"Paragraphs: {len(paragraphs)}")
    print(f"Hard Page Breaks: {len(page_breaks)}")
    print(f"Tables: {len(tables)}")
    print(f"Drawings/Figures: {len(drawings)}")
    if len(page_breaks) < 3:
        print("WARNING: Fewer than 3 hard page breaks found. Document is vulnerable to layout reflow shifts!")

audit_docx(r"D:\workspace\omission\outputs\draft\omission-2026-draft-a.docx")
```

---

## Template-Driven Generation (`docxtpl`)

When populating documents programmatically, create a styled `template.docx` with Jinja2 placeholder tags:

```python
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Inches

tpl = DocxTemplate("template.docx")

context = {
    'title': 'Omission Neurophysiology Draft',
    'abstract': 'Here is the abstract text...',
    'figure_1': InlineImage(tpl, 'outputs/figures/fig1.png', width=Inches(6.0)),
    'table_data': [
        {'area': 'V1', 'units': 420},
        {'area': 'PFC', 'units': 310}
    ]
}

tpl.render(context)
tpl.save("generated_draft.docx")
```

---

## Visual Verification Protocol

"Executes without error" is **not** layout verification. Always inspect rendering before delivery:
1. Convert `.docx` to `.pdf` (via Word COM `Word.Application` or `soffice` / `libreoffice` / `pandoc`).
2. Render PDF pages into images using `PyMuPDF` (`fitz`) or `pdf2image`.
3. Check visual page boundaries, figure positioning, and caption placement.

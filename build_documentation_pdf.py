"""
ReconcilePro Engine Documentation PDF Generator
Generates ReconcilePro_Engine_Documentation.pdf using ReportLab with custom NumberedCanvas.
Refined for publication-grade formatting, explicit section pagination, and 100% universal font safety.
"""

from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

WORKSPACE = Path(__file__).resolve().parent
PDF_OUTPUT = WORKSPACE / "ReconcilePro_Engine_Documentation.pdf"


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print 'Page X of Y' 
    and running headers on every page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        
        # Header (Pages 2+)
        if self._pageNumber > 1:
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1E3A8A"))
            self.drawString(40, 808, "RECONCILEPRO")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawString(115, 808, "|  GST Reconciliation Engine Specification (reconcile.py)")
            
            # Header line
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(40, 802, 555, 802)

        # Footer (All pages)
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(40, 28, "ReconcilePro Compliance Platform  |  Technical Reference & Audit Architecture")
        
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(555, 28, page_str)
        
        # Footer line
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(40, 38, 555, 38)
        
        self.restoreState()


def create_documentation():
    # Target printable area: A4 (595.27 x 841.89 pt), margins: 40pt
    # Printable width: 595.27 - 80 = 515.27 pt
    doc = SimpleDocTemplate(
        str(PDF_OUTPUT),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=46,
        bottomMargin=46
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette
    primary_navy = colors.HexColor("#0F172A")
    royal_blue   = colors.HexColor("#1E3A8A")
    slate_dark   = colors.HexColor("#334155")
    code_bg      = colors.HexColor("#0F172A")
    
    # Styles
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.white,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#E2E8F0"),
        spaceAfter=10
    ))
    styles.add(ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#93C5FD"),
    ))
    styles.add(ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        'SecHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12.5,
        leading=16,
        textColor=primary_navy,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        'SubSecHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=13,
        textColor=royal_blue,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    ))
    styles.add(ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=slate_dark,
        spaceAfter=5
    ))
    styles.add(ParagraphStyle(
        'BodyJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=slate_dark,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    ))
    styles.add(ParagraphStyle(
        'BulletText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=slate_dark,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=4
    ))
    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#1E3A8A"),
    ))
    styles.add(ParagraphStyle(
        'CalloutTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E40AF"),
        spaceAfter=3
    ))
    styles.add(ParagraphStyle(
        'CodeMonospace',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#E2E8F0"),
    ))
    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10.5,
        textColor=primary_navy,
        alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=slate_dark,
        alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10.5,
        textColor=primary_navy,
        alignment=TA_LEFT
    ))

    story = []

    # =========================================================================
    # PAGE 1: TITLE BANNER, SECTION 1 & SECTION 2
    # =========================================================================
    banner_data = [
        [
            Paragraph("RECONCILEPRO ENGINE ARCHITECTURE  |  TECHNICAL SPECIFICATION", ParagraphStyle('Tag', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor("#93C5FD"))),
        ],
        [
            Paragraph("reconcile.py - Core GST Reconciliation Engine", styles['DocTitle']),
        ],
        [
            Paragraph("A mathematical, algorithmic, and statutory deep-dive into automated reconciliation, schema normalization, safe duplicate resolution, and exception classification.", styles['DocSubtitle']),
        ],
        [
            Table([
                [
                    Paragraph("TARGET FILE", styles['MetaLabel']),
                    Paragraph("MODULE DIRECTORY", styles['MetaLabel']),
                    Paragraph("EXECUTION ENVIRONMENT", styles['MetaLabel']),
                    Paragraph("STATUTORY FRAMEWORK", styles['MetaLabel']),
                ],
                [
                    Paragraph("reconcile.py", styles['MetaValue']),
                    Paragraph("backend/reconciliation", styles['MetaValue']),
                    Paragraph("Python 3.10+ / Pandas / FastAPI", styles['MetaValue']),
                    Paragraph("CGST Act (Sec 16(2)(aa), Sec 50)", styles['MetaValue']),
                ]
            ], colWidths=[120, 130, 140, 105], style=[
                ('TOPPADDING', (0,0), (-1,-1), 1),
                ('BOTTOMPADDING', (0,0), (-1,-1), 1),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ])
        ]
    ]

    banner_table = Table(banner_data, colWidths=[515])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#0F172A")),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, colors.HexColor("#334155")),
        ('BOTTOMPADDING', (0, 2), (-1, 2), 6),
        ('TOPPADDING', (0, 3), (-1, 3), 6),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 10))

    # SECTION 1
    story.append(Paragraph("1. Executive Summary & Statutory Context", styles['SecHeading']))
    story.append(Paragraph(
        "Under the Indian Goods and Services Tax (GST) framework, businesses must reconcile their internal accounting records with statutory portal filings. Mismatches lead to substantial interest liabilities under Section 50 of the CGST Act and disallowance of <b>Input Tax Credit (ITC)</b> under Section 16(2)(aa).",
        styles['BodyJustify']
    ))

    dual_flow_data = [
        [
            Paragraph("<b>Outward Reconciliation (Sales)</b>", styles['CalloutTitle']),
            Paragraph("<b>Inward Reconciliation (Purchases)</b>", styles['CalloutTitle'])
        ],
        [
            Paragraph("<b>Source 1:</b> Sales Register (Books)<br/><b>Source 2:</b> GSTR-1 Portal Return<br/><b>Primary Goal:</b> Detect unfiled outward supplies, rate variances, and invoice number typos to avoid tax liability interest.", styles['CalloutText']),
            Paragraph("<b>Source 1:</b> Purchase Register (Inward Ledger)<br/><b>Source 2:</b> GSTR-2A / GSTR-2B Returns<br/><b>Primary Goal:</b> Verify vendor return filing, eliminate unfiled vendor claims, and safeguard Input Tax Credit.", styles['CalloutText'])
        ]
    ]
    dual_table = Table(dual_flow_data, colWidths=[252, 253])
    dual_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#F0F7FF")),
        ('BACKGROUND', (1,0), (1,-1), colors.HexColor("#FAF5FF")),
        ('BOX', (0,0), (0,-1), 1, colors.HexColor("#93C5FD")),
        ('BOX', (1,0), (1,-1), 1, colors.HexColor("#C4B5FD")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(dual_table)
    story.append(Spacer(1, 10))

    # SECTION 2
    story.append(Paragraph("2. Mathematical Set Partitioning Framework", styles['SecHeading']))
    story.append(Paragraph(
        "Rather than utilizing quadratic comparisons (O(N * M) nested iterations), the engine projects normalized invoice identifier strings into Python hash sets. This establishes a 3-way disjoint set partition operating in optimal <b>O(N + M) linear time</b>:",
        styles['BodyJustify']
    ))

    partition_box_data = [
        [
            Paragraph(
                "<b>Universe of Invoice Identifiers:</b> U<br/>"
                "- <b>S<sub>my</sub></b> = { inv in Books | inv != '' } &nbsp;&nbsp;&nbsp;&nbsp;- <b>S<sub>gst</sub></b> = { inv in Portal | inv != '' }<br/>"
                "<b>1. Common Intersection:</b> S<sub>common</sub> = S<sub>my</sub> (intersect) S<sub>gst</sub> -&gt; Evaluated for 1:1 Value Match, Value Mismatch, or Duplicate Collisions.<br/>"
                "<b>2. Left Asymmetric Difference:</b> S<sub>only_my</sub> = S<sub>my</sub> \\ S<sub>gst</sub> -&gt; Invoices in books but absent on GST portal (<b>MISSING_IN_GST</b>).<br/>"
                "<b>3. Right Asymmetric Difference:</b> S<sub>only_gst</sub> = S<sub>gst</sub> \\ S<sub>my</sub> -&gt; Invoices on portal but omitted in books (<b>EXTRA_IN_GST</b>).",
                styles['CalloutText']
            )
        ]
    ]
    pbox_table = Table(partition_box_data, colWidths=[515])
    pbox_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(pbox_table)

    # END OF PAGE 1
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: SECTION 3 (TAXONOMY) & SECTION 4 (_extract_gstin)
    # =========================================================================
    story.append(Paragraph("3. Classification Taxonomy & Statutory Action Matrix", styles['SecHeading']))
    story.append(Paragraph("Every invoice is tagged with a decisive status, a fine-grained discrepancy category, plausible hypotheses, and immediate remediation steps:", styles['BodyDark']))

    taxonomy_data = [
        [
            Paragraph("Status", styles['TableHeader']),
            Paragraph("Mathematical Condition", styles['TableHeader']),
            Paragraph("Discrepancy Category", styles['TableHeader']),
            Paragraph("Compliance Impact & Recommended Action", styles['TableHeader']),
        ],
        [
            Paragraph("<font color='#16A34A'><b>MATCH</b></font>", styles['TableCellBold']),
            Paragraph("inv in S<sub>common</sub><br/>dTV = 0 &amp; dGST = 0", styles['TableCell']),
            Paragraph("MATCH", styles['TableCell']),
            Paragraph("Perfect reconciliation across registers. Safe for statutory reporting; zero audit risk.", styles['TableCell']),
        ],
        [
            Paragraph("<font color='#D97706'><b>MISMATCH</b></font>", styles['TableCellBold']),
            Paragraph("inv in S<sub>common</sub><br/>dTV != 0 or dGST != 0", styles['TableCell']),
            Paragraph("TAXABLE_AND_GST_MISMATCH<br/>TAXABLE_VALUE_MISMATCH<br/>GST_AMOUNT_MISMATCH", styles['TableCell']),
            Paragraph("Data entry typo, rate variance, or unapplied credit note. Compare physical invoices; issue credit/debit note if needed.", styles['TableCell']),
        ],
        [
            Paragraph("<font color='#D97706'><b>MISMATCH</b></font>", styles['TableCellBold']),
            Paragraph("inv in S<sub>common</sub><br/>n<sub>my</sub> &gt; 1 or n<sub>gst</sub> &gt; 1", styles['TableCell']),
            Paragraph("DUPLICATE_INVOICE", styles['TableCell']),
            Paragraph("Duplicate billings detected. Multi-row preserve algorithm retains every entry to prevent silent drop and tax overpayment.", styles['TableCell']),
        ],
        [
            Paragraph("<font color='#DC2626'><b>MISSING_IN_GST</b></font>", styles['TableCellBold']),
            Paragraph("inv in S<sub>my</sub> \\ S<sub>gst</sub>", styles['TableCell']),
            Paragraph("MISSING_IN_GST", styles['TableCell']),
            Paragraph("<b>Sales:</b> Unreported outward supply (interest risk).<br/><b>Purchases:</b> Vendor has not filed GSTR-1; <b>ITC is blocked</b> under Sec 16(2)(aa). Contact vendor.", styles['TableCell']),
        ],
        [
            Paragraph("<font color='#7C3AED'><b>EXTRA_IN_GST</b></font>", styles['TableCellBold']),
            Paragraph("inv in S<sub>gst</sub> \\ S<sub>my</sub>", styles['TableCell']),
            Paragraph("EXTRA_IN_GST", styles['TableCell']),
            Paragraph("Unbooked invoice on portal or incorrect recipient GSTIN. Verify delivery challans; enter in purchase journal or reject bill.", styles['TableCell']),
        ],
    ]

    tax_table = Table(taxonomy_data, colWidths=[80, 105, 135, 195], repeatRows=1)
    tax_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(tax_table)
    story.append(Spacer(1, 12))

    # SECTION 4
    story.append(Paragraph("4. Function Deep Dive: _extract_gstin(row)", styles['SecHeading']))
    story.append(Paragraph(
        "<b>Signature:</b> <font face='Courier' color='#1E3A8A'>_extract_gstin(row) -&gt; str</font><br/>"
        "Normalizes and extracts the 15-character Goods and Services Taxpayer Identification Number (GSTIN) from diverse data row structures.",
        styles['BodyDark']
    ))

    code_extract = (
        "def _extract_gstin(row) -> str:\n"
        "    if hasattr(row, \"get\"):\n"
        "        return str(row.get(\"gstin\") or row.get(\"customer_gstin\") or row.get(\"supplier_gstin\") or \"\").strip()\n"
        "    return \"\""
    )
    code_table = Table([[Preformatted(code_extract, styles['CodeMonospace'])]], colWidths=[515])
    code_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1E293B")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(code_table)
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Detailed Working & Design Mechanics:</b>", styles['SubSecHeading']))
    story.append(Paragraph("- <b>Polymorphic Type Guarding:</b> Evaluates <code>hasattr(row, 'get')</code> so the function safely processes Python dictionaries (from JSON/API payloads) and Pandas <code>Series</code> objects identically without raising <code>AttributeError</code>.", styles['BulletText']))
    story.append(Paragraph("- <b>Short-Circuit Priority Resolution:</b> Evaluates schema variations in order of frequency: <code>'gstin'</code> -&gt; <code>'customer_gstin'</code> (outward registers) -&gt; <code>'supplier_gstin'</code> (inward registers). The first truthy value is selected.", styles['BulletText']))
    story.append(Paragraph("- <b>Sanitization & Defensive Strip:</b> Converts any value into a string and applies <code>.strip()</code> to eradicate trailing spaces, newline symbols, or whitespace artifacts resulting from CSV/Excel parsing.", styles['BulletText']))

    # END OF PAGE 2
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: SECTION 5 (reconcile() DEEP DIVE)
    # =========================================================================
    story.append(Paragraph("5. Function Deep Dive: reconcile(my_source, gst_source)", styles['SecHeading']))
    story.append(Paragraph(
        "<b>Signature:</b> <font face='Courier' color='#1E3A8A'>reconcile(my_source, gst_source) -&gt; pd.DataFrame</font><br/>"
        "The primary reconciliation engine. Accepts either in-memory Pandas DataFrames or on-disk file paths, executing bidirectional comparison across eight structured execution phases.",
        styles['BodyDark']
    ))

    phases = [
        ("Phase 1: Input Ingestion & Isolation",
         "Checks <code>isinstance(source, pd.DataFrame)</code>. If True, invokes <code>.copy()</code> to guarantee functional immutability (ensures caller DataFrames from the API router are never mutated). If False, loads CSV from the project <code>data/</code> folder using <code>pd.read_csv()</code>."),
        
        ("Phase 2: Schema Validation & Defensive Imputation",
         "Checks for mandatory columns: <code>invoice_no</code>, <code>invoice_date</code>, <code>gstin</code>, <code>taxable_value</code>, <code>gst_amount</code>. If any column is absent from user uploads, it is defensively initialized as <code>pd.Series(dtype=object)</code> to prevent downstream runtime <code>KeyError</code> crashes."),

        ("Phase 3: Identifier Cleansing & Pruning",
         "Converts invoice numbers to strings (<code>astype(str).str.strip()</code>) to guarantee uniform types. Prunes blank/placeholder rows where <code>invoice_no == ''</code> to eliminate phantom records."),

        ("Phase 4: Set Theory Partitioning",
         "Generates unique hash sets <code>my_inv</code> and <code>gst_inv</code>. Computes <code>common = my_inv & gst_inv</code>, <code>only_my = my_inv - gst_inv</code>, and <code>only_gst = gst_inv - my_inv</code> in linear time."),

        ("Phase 5: 1-to-1 Discrepancy & Tolerance Verification",
         "For common invoices with exactly one entry on each side (<code>n_my == 1 and n_gst == 1</code>), computes rounded arithmetic differences: <code>tv_diff = round(a_tv - b_tv, 2)</code> and <code>gst_diff = round(a_gst - b_gst, 2)</code>. If differences equal zero, assigns <code>MATCH</code>; otherwise assigns <code>MISMATCH</code> with tailored root-cause hypotheses."),

        ("Phase 6: Safe Duplicate Handling (Fixing the .iloc[0] Data Drop Bug)",
         "If an invoice number appears more than once on either side (<code>n_my > 1 or n_gst > 1</code>), naive implementations call <code>.iloc[0]</code> and silently discard duplicate rows. ReconcilePro iterates up to <code>max(n_my, n_gst)</code>, pairing matching rows where available and preserving every duplicate entry as an individual audit row tagged <code>DUPLICATE_INVOICE</code>."),

        ("Phase 7: Partition Asymmetries (MISSING_IN_GST & EXTRA_IN_GST)",
         "Iterates over <code>only_my</code> and <code>only_gst</code>. For <code>MISSING_IN_GST</code>, generates notifications regarding unfiled sales or blocked vendor ITC. For <code>EXTRA_IN_GST</code>, suggests checking delivery challans or notifying vendors of wrong GSTIN usage."),

        ("Phase 8: Structured DataFrame Construction",
         "Aggregates all compiled audit dictionaries into a clean Pandas DataFrame ready for frontend presentation, Excel/CSV export, and ML anomaly scoring.")
    ]

    for title, desc in phases:
        story.append(Paragraph(f"<b>- {title}:</b> {desc}", styles['BulletText']))

    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Zero-Loss Duplicate Preservation Implementation:</b>", styles['SubSecHeading']))
    code_dupl = (
        "else:\n"
        "    # Safe duplicate handling: preserve every row without silent .iloc[0] drop\n"
        "    max_len = max(n_my, n_gst)\n"
        "    for idx in range(max_len):\n"
        "        a = my_matches.iloc[idx] if idx < n_my else None\n"
        "        b = gst_matches.iloc[idx] if idx < n_gst else None\n"
        "        a_tv = float(a[\"taxable_value\"]) if a is not None else None\n"
        "        b_tv = float(b[\"taxable_value\"]) if b is not None else None\n"
        "        tv_diff = round(a_tv - b_tv, 2) if (a_tv is not None and b_tv is not None) else None\n"
        "        explanation = f\"Duplicate invoice number '{inv}' detected ({n_my} in books, {n_gst} in GST).\"\n"
        "        # Appends all individual rows to results list ensuring complete audit visibility"
    )
    code_dupl_table = Table([[Preformatted(code_dupl, styles['CodeMonospace'])]], colWidths=[515])
    code_dupl_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1E293B")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(code_dupl_table)

    # END OF PAGE 3
    story.append(PageBreak())

    # =========================================================================
    # PAGE 4: SECTION 6 (show_result) & SECTION 7 (SYSTEM INTEGRATION)
    # =========================================================================
    story.append(Paragraph("6. Function Deep Dive: show_result & CLI Entry Point", styles['SecHeading']))
    story.append(Paragraph(
        "<b>Signature:</b> <font face='Courier' color='#1E3A8A'>show_result(title, df) -&gt; None</font><br/>"
        "Outputs terminal formatting, displays tabular results without index numbers (<code>to_string(index=False)</code>), and prints a frequency distribution of reconciliation statuses via <code>df['status'].value_counts()</code>.",
        styles['BodyDark']
    ))

    code_show = (
        "def show_result(title, df):\n"
        "    print(\"\\n\" + \"=\" * 60)\n"
        "    print(title)\n"
        "    print(\"=\" * 60)\n"
        "    print(df.to_string(index=False))\n"
        "    print(\"\\nSummary:\")\n"
        "    print(df[\"status\"].value_counts())\n\n"
        "if __name__ == \"__main__\":\n"
        "    sales_result = reconcile(\"sales_register.csv\", \"gstr1.csv\")\n"
        "    purchase_result = reconcile(\"purchase_register.csv\", \"gstr2a.csv\")\n"
        "    show_result(\"SALES RECONCILIATION: SALES REGISTER vs GSTR-1\", sales_result)\n"
        "    show_result(\"PURCHASE RECONCILIATION: PURCHASE REGISTER vs GSTR-2A\", purchase_result)"
    )
    code_show_table = Table([[Preformatted(code_show, styles['CodeMonospace'])]], colWidths=[515])
    code_show_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), code_bg),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#1E293B")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(code_show_table)
    story.append(Spacer(1, 10))

    # SECTION 7
    story.append(Paragraph("7. End-to-End System Integration Architecture", styles['SecHeading']))
    story.append(Paragraph(
        "Within the ReconcilePro production stack, <code>reconcile.py</code> is cleanly decoupled from storage, serving as an in-memory computational engine:",
        styles['BodyJustify']
    ))

    integration_steps = [
        ("Step 1: REST Request", "The React client initiates a call to <code>GET /reconcile?tax_period=YYYY-MM&purchase_source=gstr2a</code> with Bearer JWT credentials."),
        ("Step 2: Tenant Isolation & Ingestion", "FastAPI's dependency injector authenticates the business tenant, queries PostgreSQL/SQLite for tenant invoices in that period, and constructs in-memory DataFrames for both registers."),
        ("Step 3: Core Engine Execution", "The route handler executes <code>reconcile(my_df, gst_df)</code>. The engine completes set partitioning and variance calculation in milliseconds."),
        ("Step 4: Machine Learning Anomaly Detection", "The resulting audit DataFrame is passed to <code>services/ml_service.py</code>, which runs an Isolation Forest and rule-based risk model, generating normalized Risk Scores (0-100) and tagging suspicious tax ratios."),
        ("Step 5: Client Dashboard & Statutory Reports", "The API returns the unified dataset to the React frontend for interactive filtering, KPI cards, and statutory PDF/Excel exports.")
    ]
    for step_title, step_desc in integration_steps:
        story.append(Paragraph(f"<b>- {step_title}:</b> {step_desc}", styles['BulletText']))

    # END OF PAGE 4
    story.append(PageBreak())

    # =========================================================================
    # PAGE 5: SECTION 8 (COMPLETE OUTPUT SCHEMA REFERENCE)
    # =========================================================================
    story.append(Paragraph("8. Complete Output Schema Reference Table", styles['SecHeading']))
    story.append(Paragraph("The DataFrame returned by <code>reconcile()</code> provides 16 standardized audit columns, powering both frontend UI views and statutory audit exports:", styles['BodyDark']))

    schema_data = [
        [
            Paragraph("Column Name", styles['TableHeader']),
            Paragraph("Data Type", styles['TableHeader']),
            Paragraph("Sample / Domain", styles['TableHeader']),
            Paragraph("Functional Role & Business Meaning", styles['TableHeader']),
        ],
        [
            Paragraph("<b>invoice_no</b>", styles['TableCellBold']),
            Paragraph("String", styles['TableCell']),
            Paragraph("INV-2026-001", styles['TableCell']),
            Paragraph("Cleaned alphanumeric invoice number; primary matching key.", styles['TableCell']),
        ],
        [
            Paragraph("<b>invoice_date</b>", styles['TableCellBold']),
            Paragraph("String (YYYY-MM-DD)", styles['TableCell']),
            Paragraph("2026-07-15", styles['TableCell']),
            Paragraph("Invoice date from books or portal filing.", styles['TableCell']),
        ],
        [
            Paragraph("<b>gstin</b>", styles['TableCellBold']),
            Paragraph("String (15-char)", styles['TableCell']),
            Paragraph("29AAAAA0000A1Z5", styles['TableCell']),
            Paragraph("Counterparty customer/supplier GSTIN resolved via <code>_extract_gstin</code>.", styles['TableCell']),
        ],
        [
            Paragraph("<b>taxable_value</b>", styles['TableCellBold']),
            Paragraph("Float", styles['TableCell']),
            Paragraph("100000.00", styles['TableCell']),
            Paragraph("Display taxable value (defaults to books; falls back to portal).", styles['TableCell']),
        ],
        [
            Paragraph("<b>gst_amount</b>", styles['TableCellBold']),
            Paragraph("Float", styles['TableCell']),
            Paragraph("18000.00", styles['TableCell']),
            Paragraph("Display GST amount (defaults to books; falls back to portal).", styles['TableCell']),
        ],
        [
            Paragraph("<b>expected_taxable_value</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("100000.00", styles['TableCell']),
            Paragraph("Taxable value according to internal ledger.", styles['TableCell']),
        ],
        [
            Paragraph("<b>actual_taxable_value</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("95000.00", styles['TableCell']),
            Paragraph("Taxable value according to filed GST portal return.", styles['TableCell']),
        ],
        [
            Paragraph("<b>expected_gst_amount</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("18000.00", styles['TableCell']),
            Paragraph("Total GST (CGST + SGST + IGST) according to internal ledger.", styles['TableCell']),
        ],
        [
            Paragraph("<b>actual_gst_amount</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("17100.00", styles['TableCell']),
            Paragraph("Total GST according to filed GST portal return.", styles['TableCell']),
        ],
        [
            Paragraph("<b>status</b>", styles['TableCellBold']),
            Paragraph("Enum String", styles['TableCell']),
            Paragraph("MATCH / MISMATCH", styles['TableCell']),
            Paragraph("High-level status: <code>MATCH</code>, <code>MISMATCH</code>, <code>MISSING_IN_GST</code>, <code>EXTRA_IN_GST</code>.", styles['TableCell']),
        ],
        [
            Paragraph("<b>taxable_value_diff</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("5000.00", styles['TableCell']),
            Paragraph("Arithmetic difference: <code>round(expected_tv - actual_tv, 2)</code>.", styles['TableCell']),
        ],
        [
            Paragraph("<b>gst_amount_diff</b>", styles['TableCellBold']),
            Paragraph("Float / None", styles['TableCell']),
            Paragraph("900.00", styles['TableCell']),
            Paragraph("Arithmetic difference: <code>round(expected_gst - actual_gst, 2)</code>.", styles['TableCell']),
        ],
        [
            Paragraph("<b>explanation</b>", styles['TableCellBold']),
            Paragraph("String", styles['TableCell']),
            Paragraph("Audit sentence", styles['TableCell']),
            Paragraph("Human-readable statement detailing exact rupee variances.", styles['TableCell']),
        ],
        [
            Paragraph("<b>discrepancy_category</b>", styles['TableCellBold']),
            Paragraph("Enum String", styles['TableCell']),
            Paragraph("TAXABLE_AND_GST...", styles['TableCell']),
            Paragraph("Fine-grained taxonomy category for automated reporting & filtering.", styles['TableCell']),
        ],
        [
            Paragraph("<b>possible_causes</b>", styles['TableCellBold']),
            Paragraph("List[String]", styles['TableCell']),
            Paragraph("Hypotheses list", styles['TableCell']),
            Paragraph("Root-cause hypotheses (e.g. rate mismatch, credit note omission).", styles['TableCell']),
        ],
        [
            Paragraph("<b>suggested_action</b>", styles['TableCellBold']),
            Paragraph("String", styles['TableCell']),
            Paragraph("Action item", styles['TableCell']),
            Paragraph("Immediate corrective action for the finance/accounting team.", styles['TableCell']),
        ],
    ]

    schema_table = Table(schema_data, colWidths=[105, 80, 100, 230], repeatRows=1)
    schema_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#F1F5F9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0,0), (-1,-1), 3.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3.5),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(schema_table)

    # Build Document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated: {PDF_OUTPUT} ({PDF_OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    create_documentation()

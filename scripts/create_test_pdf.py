#!/usr/bin/env python3
"""
Create test PDF document for converter testing.
"""

from pathlib import Path

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    print("reportlab is required. Install it with: pip install reportlab")
    exit(1)


def create_test_pdf(output_path: str):
    """
    Create a test PDF document with Russian court document content.

    Args:
        output_path: Path to save PDF file
    """
    # Create PDF
    pdf = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Try to use system fonts for Cyrillic
    try:
        # Try common Russian font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",  # Windows
        ]

        for font_path in font_paths:
            if Path(font_path).exists():
                pdfmetrics.registerFont(TTFont('DejaVu', font_path))
                pdf.setFont('DejaVu', 12)
                break
        else:
            # Fallback to default font
            pdf.setFont('Helvetica', 12)
    except:
        pdf.setFont('Helvetica', 12)

    # Add content (court document sample)
    y_position = height - 50

    # Title
    pdf.setFontSize(14)
    pdf.drawString(50, y_position, "АРБИТРАЖНЫЙ СУД ГОРОДА МОСКВЫ")
    y_position -= 30

    pdf.setFontSize(12)
    pdf.drawString(50, y_position, "115191, г.Москва, ул. Большая Тульская, д. 17")
    y_position -= 40

    # Case number
    pdf.setFontSize(14)
    pdf.drawString(50, y_position, "РЕШЕНИЕ")
    y_position -= 25

    pdf.setFontSize(11)
    pdf.drawString(50, y_position, "Именем Российской Федерации")
    y_position -= 40

    pdf.setFontSize(12)
    pdf.drawString(50, y_position, "г. Москва                                    15 января 2024 года")
    y_position -= 25

    pdf.drawString(50, y_position, "Дело № А40-12345/24")
    y_position -= 40

    # Court composition
    lines = [
        "Арбитражный суд города Москвы в составе:",
        "судьи Иванова И.И.,",
        "при ведении протокола судебного заседания секретарем Петровой П.П.,",
        "",
        "рассмотрев в судебном заседании дело по иску",
        "ООО \"Компания\" (ОГРН 1234567890123, ИНН 1234567890)",
        "к ООО \"Контрагент\" (ОГРН 9876543210987, ИНН 9876543210)",
        "о взыскании задолженности по договору поставки",
        "",
        "УСТАНОВИЛ:",
        "",
        "Истец обратился в арбитражный суд с требованием о взыскании",
        "задолженности в размере 1 000 000 рублей по договору поставки",
        "№ 123 от 01.06.2023.",
        "",
        "В судебном заседании установлено, что ответчик получил товар,",
        "но оплату не произвел.",
        "",
        "Руководствуясь статьями 167-170, 176 Арбитражного процессуального",
        "кодекса Российской Федерации, арбитражный суд",
        "",
        "РЕШИЛ:",
        "",
        "Исковые требования удовлетворить.",
        "Взыскать с ООО \"Контрагент\" в пользу ООО \"Компания\"",
        "задолженность в размере 1 000 000 рублей,",
        "расходы по уплате государственной пошлины 23 000 рублей.",
    ]

    for line in lines:
        if y_position < 100:  # New page if needed
            pdf.showPage()
            pdf.setFont('Helvetica', 12)
            y_position = height - 50

        pdf.drawString(50, y_position, line)
        y_position -= 20

    # Signature
    if y_position < 150:
        pdf.showPage()
        pdf.setFont('Helvetica', 12)
        y_position = height - 50

    y_position -= 20
    pdf.drawString(50, y_position, "Судья                          И.И. Иванов")

    # Save PDF
    pdf.save()

    print(f"✓ Created test PDF: {output_path}")
    print(f"  Size: {Path(output_path).stat().st_size:,} bytes")


if __name__ == "__main__":
    import sys

    output_file = sys.argv[1] if len(sys.argv) > 1 else "tests/data/test_document.pdf"

    # Create output directory
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    create_test_pdf(output_file)

# nano-pdf — PDF Skill

**Venv:** `~/.openclaw/tools-venv/bin/python`  
**Libraries:** `reportlab` (создание), `fitz` / PyMuPDF (чтение, правка, рендер)

---

## 1. Создать PDF из текста

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Кириллица — зарегистрировать шрифт (DejaVu есть в системе)
pdfmetrics.registerFont(TTFont('DejaVu', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))

doc = SimpleDocTemplate("/tmp/out.pdf", pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=20*mm, bottomMargin=20*mm)
styles = getSampleStyleSheet()
normal = ParagraphStyle('normal', fontName='DejaVu', fontSize=11, leading=16)
title  = ParagraphStyle('title',  fontName='DejaVu', fontSize=16, leading=22, spaceAfter=6*mm)

story = [
    Paragraph("Заголовок документа", title),
    Paragraph("Текст первого абзаца...", normal),
    Spacer(1, 5*mm),
    Paragraph("Текст второго абзаца...", normal),
]
doc.build(story)
```

## 2. Прочитать текст из PDF

```python
import fitz  # PyMuPDF

doc = fitz.open("/path/to/file.pdf")
for page in doc:
    print(page.get_text())
doc.close()
```

Или через CLI: `pdftotext /path/file.pdf /path/out.txt`

## 3. Рендер PDF → PNG

```python
import fitz

doc = fitz.open("/path/to/file.pdf")
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=150)
    pix.save(f"/tmp/page_{i:03d}.png")
doc.close()
```

Или через CLI: `pdftoppm -r 150 -png /path/file.pdf /tmp/page`

## 4. Добавить аннотацию / штамп на страницу

```python
import fitz
from datetime import date

doc = fitz.open("/path/to/file.pdf")
page = doc[0]  # первая страница
rect = fitz.Rect(10, 10, 200, 40)  # x0, y0, x1, y1 в points
annot = page.add_rect_annot(rect)
annot.set_info(content="Проверено " + str(date.today()))
annot.update()
doc.save("/path/to/out.pdf")
doc.close()
```

## 5. Объединить несколько PDF

```python
import fitz

result = fitz.open()
for path in ["/tmp/a.pdf", "/tmp/b.pdf", "/tmp/c.pdf"]:
    src = fitz.open(path)
    result.insert_pdf(src)
    src.close()
result.save("/tmp/merged.pdf")
result.close()
```

## 6. Извлечь страницы (диапазон)

```python
import fitz

src = fitz.open("/path/to/file.pdf")
result = fitz.open()
result.insert_pdf(src, from_page=2, to_page=5)  # страницы 3–6 (0-based)
result.save("/tmp/extract.pdf")
```

---

## Заметки

- Все пути передавать абсолютными.
- Для сложной вёрстки с таблицами использовать `reportlab.platypus.Table`.
- Если шрифт DejaVu не найден: `fc-list | grep -i deja`
- PyMuPDF координаты — в points (1 pt = 1/72 дюйма), начало — верхний левый угол.

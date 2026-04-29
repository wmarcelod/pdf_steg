"""Generate a small sample PDF for testing pdf_steg."""
from pathlib import Path
import fitz

doc = fitz.open()
page = doc.new_page()  # default Letter
text = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
    "nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in "
    "reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla "
    "pariatur. Excepteur sint occaecat cupidatat non proident, sunt in "
    "culpa qui officia deserunt mollit anim id est laborum."
)
page.insert_textbox(fitz.Rect(50, 60, 560, 740), text, fontsize=12, fontname="helv")
out = Path(__file__).with_name("sample.pdf")
doc.save(out)
print(f"wrote {out}")

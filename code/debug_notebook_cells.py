
import nbformat

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = nbformat.read(f, as_version=4)

print("Listing code cells:")
for i, cell in enumerate(nb.cells):
    if cell.cell_type == 'code':
        source = cell.source
        first_line = source.split('\n')[0] if source else "EMPTY"
        print(f"Cell {i}: {first_line[:50]}...")

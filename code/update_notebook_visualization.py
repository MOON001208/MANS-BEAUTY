
import nbformat
import os

notebook_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\Gemini_Keywords_Topic_Modeling.ipynb'
visualization_code_path = r'c:\Users\USER\Documents\웅진씽크빅kdt\남성화장품시장분석\code\visualization_code.py'

def update_notebook():
    if not os.path.exists(notebook_path):
        print(f"Error: Notebook not found at {notebook_path}")
        return

    if not os.path.exists(visualization_code_path):
        print(f"Error: Visualization code file not found at {visualization_code_path}")
        return

    # Read the new visualization code
    with open(visualization_code_path, 'r', encoding='utf-8') as f:
        new_viz_code = f.read()

    # Read the notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)

    # Find the cell to replace
    # We look for the cell containing the comment "# 2. 페르소나별 키워드 시각화"
    found = False
    for cell in nb.cells:
        if cell.cell_type == 'code':
            if "# 2. 페르소나별 키워드 시각화" in cell.source:
                print("Found visualization cell. Updating content...")
                cell.source = new_viz_code
                found = True
                break
    
    if not found:
        print("Warning: Target visualization cell not found. Appending new cell instead.")
        new_cell = nbformat.v4.new_code_cell(new_viz_code)
        nb.cells.append(new_cell)

    # Save the notebook
    with open(notebook_path, 'w', encoding='utf-8') as f:
        nbformat.write(nb, f)
    
    print(f"Successfully updated notebook: {notebook_path}")

if __name__ == '__main__':
    update_notebook()

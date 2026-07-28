import sys
import pdfplumber

def is_table_page(page):
    """
    Check for the presence of lines that indicate a table structure
    """
    tables = page.find_tables()
    return len(tables) > 0


def extract_table(page):
    """
    Extract the table from a particular page
    """
    # Table settings to handle multi-line cells and merged rows
    table_settings = {
        "vertical_strategy": "lines", 
        "horizontal_strategy": "lines",
        "join_y_tolerance": 5,      # Helps merge text vertically split across lines
        "join_x_tolerance": 2,
        "explicit_vertical_lines": [],
        "explicit_horizontal_lines": [],
        "snap_y_tolerance": 3,
    }
    tables = page.extract_tables(table_settings=table_settings)
    
    if not tables:
        return "No tables detected."

    output = []
    for table in tables:
        for row in table:
            # Clean up: Replace None with empty string and 
            # use replace('\n', ' ') to keep multi-line cell content in one cell
            cleaned_row = [
                (cell.replace('\n', ' ') if cell else "") 
                for cell in row
            ]
            # Join with a pipe and padding to match your visual format
            output.append(" | ".join(cleaned_row))
    
    return "\n".join(output)


def map_pdf(pdf, max_page_number=100):
    """
    Map out our pdf
    """
    to_return = {}

    for index, page in enumerate(pdf.pages):
        # If we have exceeded our maximum number of pages to parse, break
        if index >= max_page_number:
            break

    return to_return


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script_name.py <path_to_pdf>")
    else:
        try:
            with pdfplumber.open(sys.argv[1]) as pdf:
                if not pdf.pages:
                    print("The PDF is empty.")
                else:
                    for index, page in enumerate(pdf.pages):
                        if is_table_page(page):
                            print(f"Table detected on page {index + 1}")
                            print(extract_table(page))
                            break  # Stop after the first table page is found
        except Exception as e:
            print(f"An error occurred while opening the PDF: {e}")

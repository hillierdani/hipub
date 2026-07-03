import re
from docx import Document
import fire


def convert(input_docx, output_docx="marked_document.docx", output_ris="zotero_import.ris"):
    """
    Converts Perplexity inline citations to Zotero RTF tokens.
    Natively detects both plain text references and hidden Word ordered lists anywhere in the file.
    """
    doc = Document(input_docx)

    ref_map = {}
    native_list_counter = 1

    # Strict regex patterns to identify reference items
    text_ref_pattern = re.compile(r'^(\d+)\.\s+(https?://\S+)')
    url_only_pattern = re.compile(r'^https?://\S+')

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # Case 1: Plain text numbered references (e.g., "88. https://...")
        text_match = text_ref_pattern.match(text)
        if text_match:
            ref_num = text_match.group(1)
            url = text_match.group(2).rstrip('.,] )')
            ref_map[ref_num] = url
            continue

        # Case 2: Native Word Ordered List items (where the number is hidden in XML)
        # We look for the underlying Word XML 'numPr' tag or a List style name
        is_native_list = bool(para._element.xpath('./w:pPr/w:numPr')) or para.style.name.startswith('List Number')

        if is_native_list and url_only_pattern.match(text):
            url = text.rstrip('.,] )')
            # Fallback to sequential counting matching the list layout
            ref_map[str(native_list_counter)] = url
            native_list_counter += 1

    if not ref_map:
        print("❌ Error: Could not find any references (text or native lists) containing URLs.")
        return

    print(f"📊 Successfully parsed {len(ref_map)} references from the document structure.")

    # Swap out inline bracket markers [298] with RTF tokens {Ref298, 2026}
    inline_pattern = re.compile(r'\[(\d+)\]')

    for para in doc.paragraphs:
        if inline_pattern.search(para.text):
            para.text = inline_pattern.sub(r'{Ref\1, 2026}', para.text)

    doc.save(output_docx)
    print(f"📝 Marked-up document saved to: {output_docx}")

    # Build matching RIS library registry
    with open(output_ris, 'w', encoding='utf-8') as ris_file:
        for ref_num, url in ref_map.items():
            ris_file.write("TY  - ELEC\n")
            ris_file.write(f"AU  - Ref{ref_num}\n")
            ris_file.write("PY  - 2026\n")
            ris_file.write(f"TI  - Perplexity Link {ref_num}\n")
            ris_file.write(f"UR  - {url}\n")
            ris_file.write("ER  - \n\n")

    print(f"💾 Reference RIS file saved to: {output_ris}")


if __name__ == '__main__':
    fire.Fire(convert)
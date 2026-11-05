"""Deterministic authored PDF source fixtures; no network or downloaded documents."""
from io import BytesIO
import json
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import NameObject, DictionaryObject, DecodedStreamObject

ROOT = Path(__file__).resolve().parents[1] / 'fixtures/evaluation'


def render_manual(lines_by_page):
    writer = PdfWriter()
    for lines in lines_by_page:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): writer._add_object(font)})})
        commands = ['BT /F1 11 Tf 40 780 Td 20 TL']
        for index, line in enumerate(lines):
            escaped = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.append(('T* ' if index else '') + f'({escaped}) Tj')
        commands.append('ET')
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def main():
    from hashlib import sha256
    data = json.loads((ROOT/'manuals.json').read_text())
    for manual in data['manuals']:
        source_id = 'synthetic:pdf:'+manual['slug']
        target = ROOT/'pdf'/(sha256(source_id.encode()).hexdigest()+'.pdf')
        target.write_bytes(render_manual(manual['pages']))
        print(f'{manual["slug"]}: {sha256(target.read_bytes()).hexdigest()}')


if __name__ == '__main__':
    main()

"""Synthetic OpenXML workbooks, never real historical prices."""
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

from app.importing.prices import FIELDS


def entry(**changes):
    return {'ID': '1', 'Produttore': 'IBM', 'Modello': 'PC 5150', 'Anno lancio': '1981',
        'Prezzo al lancio': '1000.5', 'Valuta': 'USD', 'Mercato / Paese': 'USA',
        'Configurazione cui si riferisce': 'Synthetic configuration with monitor',
        'Altri listini / varianti': 'Synthetic other variant: 1500 USD',
        'Fonte URL': 'https://example.org/synthetic-price-list', 'Affidabilità fonte': 'Alta',
        'Stato ricerca': 'Prezzo con fonte', 'Note': 'Synthetic fixture; not a historical value', **changes}


def workbook(entries=None, *, formula=False, sheet_name='Prezzi per modello', extra_sheet=False):
    entries = [entry()] if entries is None else entries
    main = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    document_rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package_rel = 'http://schemas.openxmlformats.org/package/2006/relationships'
    def sheet(rows):
        root = ET.Element('worksheet', xmlns=main)
        data = ET.SubElement(root, 'sheetData')
        for position, values in enumerate(rows, 1):
            row = ET.SubElement(data, 'row', r=str(position))
            for index, value in enumerate(values):
                cell = ET.SubElement(row, 'c', r=f'{chr(65 + index)}{position}', t='inlineStr')
                ET.SubElement(ET.SubElement(cell, 'is'), 't').text = str(value)
                if formula and position == 2 and index == 4:
                    ET.SubElement(cell, 'f').text = 'SUM(1,2)'
        return ET.tostring(root, encoding='utf-8')
    root = ET.Element('workbook', xmlns=main)
    sheets = ET.SubElement(root, 'sheets')
    ET.SubElement(sheets, 'sheet', name=sheet_name, sheetId='5', attrib={'{' + document_rel + '}id': 'rId5'})
    rels = ET.Element('Relationships', xmlns=package_rel)
    ET.SubElement(rels, 'Relationship', Id='rId5', Type=document_rel + '/worksheet', Target='worksheets/sheet5.xml')
    if extra_sheet:
        ET.SubElement(sheets, 'sheet', name='Quinta ricerca estesa', sheetId='6', attrib={'{' + document_rel + '}id': 'rId6'})
        ET.SubElement(rels, 'Relationship', Id='rId6', Type=document_rel + '/worksheet', Target='worksheets/sheet6.xml')
    result = BytesIO()
    with ZipFile(result, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('xl/workbook.xml', ET.tostring(root, encoding='utf-8'))
        archive.writestr('xl/_rels/workbook.xml.rels', ET.tostring(rels, encoding='utf-8'))
        archive.writestr('xl/worksheets/sheet5.xml', sheet([FIELDS] + [[item.get(field, '') for field in FIELDS] for item in entries]))
        if extra_sheet:
            archive.writestr('xl/worksheets/sheet6.xml', sheet([FIELDS] + [[item.get(field, '') for field in FIELDS] for item in entries]))
    return result.getvalue()


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('manufacturer')
    parser.add_argument('model_prefix')
    args = parser.parse_args()
    rows = [entry(**{'Produttore': args.manufacturer, 'Modello': args.model_prefix + '-A',
        'Fonte URL': 'Synthetic alternate configuration', 'Altri listini / varianti': 'Alta',
        'Affidabilità fonte': 'https://example.org/synthetic-price-list'}),
        entry(**{'Produttore': args.manufacturer, 'Modello': args.model_prefix + '-B',
            'Prezzo al lancio': '42', 'Valuta': 'GBP', 'Mercato / Paese': 'Regno Unito',
            'Stato ricerca': "Listino d'epoca, non lancio"}),
        entry(**{'Produttore': args.manufacturer, 'Modello': args.model_prefix + '-C',
            'Stato ricerca': 'Prezzo della famiglia/variante diversa'}),
        entry(**{'Produttore': args.manufacturer, 'Modello': args.model_prefix + '-D',
            'Prezzo al lancio': '', 'Stato ricerca': 'Da ricercare'})]
    args.output.write_bytes(workbook(rows, extra_sheet=True))

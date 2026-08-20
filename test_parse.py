import csv
import re

def clean_relation(val):
    if not val: return None
    # Can be multiple separated by comma?
    # Actually, Notion CSV separates multiple relations with commas.
    # Let's see if there are any quotes around them.
    # CSV reader handles quotes.
    items = []
    for item in val.split(','):
        item = item.strip()
        m = re.match(r'^(.*?)\s*\(.*?\)$', item)
        if m:
            items.append(m.group(1).strip())
        else:
            items.append(item)
    return items[0] if items else None

with open('/home/fabricio/Downloads/ExportBlock-f9f309e1-127f-4837-a970-4f3c683619bc-Part-1/Game Room/Jogos 1b13b820c62081eaab82d6f523a01417_all.csv', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print("Columns:", reader.fieldnames)
    for i, row in enumerate(reader):
        if i >= 5: break
        print(f"Row {i}:")
        print(" Title:", row.get('Jogo'))
        print(" Status:", row.get('Status'))
        print(" Genre:", clean_relation(row.get('Gênero')))
        print(" Platform:", clean_relation(row.get('Plataforma')))
        print(" Dev:", row.get('Desenvolvedora'))
        print(" HLTB:", row.get('Expectativa de Horas'))
        print(" Played:", row.get('Horas Jogadas'))
        print(" Score:", row.get('Nota'))
        print(" Platinum:", row.get('Data da Platina'))
        print(" Finish:", row.get('Data de Finalização'))
        print(" Play count:", row.get('Vez jogada'))

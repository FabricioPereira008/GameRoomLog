import os

def refactor2():
    # 7. category_detail_view.py
    f = 'frontend_desktop/views/components/category_detail_view.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'self.title_label.setStyleSheet("font-size: 24px; font-weight: 800; color: #ffffff;")',
        'self.title_label.setProperty("class", "view-title-xl")'
    )
    content = content.replace(
        'section_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff; margin-top: 8px;")',
        'section_label.setProperty("class", "section-header-small")'
    )
    with open(f, 'w') as file:
        file.write(content)

    # 8. yearbook_view.py
    f = 'frontend_desktop/views/components/yearbook_view.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'icon_label.setStyleSheet("font-size: 20px;")',
        'icon_label.setProperty("class", "yearbook-icon")'
    )
    content = content.replace(
        'title.setStyleSheet("font-size: 20px; font-weight: bold; color: #fffffe;")',
        'title.setProperty("class", "yearbook-title")'
    )
    content = content.replace(
        'year_label.setStyleSheet("color: #94a1b2; font-weight: bold;")',
        'year_label.setProperty("class", "yearbook-year")'
    )
    content = content.replace(
        'sub_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #fffffe; margin-top: 10px;")',
        'sub_label.setProperty("class", "yearbook-subtitle")'
    )
    with open(f, 'w') as file:
        file.write(content)
        
refactor2()

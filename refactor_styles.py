import os
import re

def replace_inline_styles():
    print("Starting style refactoring...")
    
    # 1. sidebar.py
    f = 'frontend_desktop/views/components/sidebar.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'version_label.setStyleSheet("color: #6b7280; font-size: 10px; text-align: center; padding-top: 4px;")',
        'version_label.setObjectName("appVersion")'
    )
    with open(f, 'w') as file:
        file.write(content)

    # 2. game_room_view.py
    f = 'frontend_desktop/views/components/game_room_view.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'now_header.setStyleSheet("font-size: 17px; font-weight: bold; color: #fffffe;")',
        'now_header.setProperty("class", "section-header")'
    )
    content = content.replace(
        'queue_header.setStyleSheet("font-size: 17px; font-weight: bold; color: #fffffe;")',
        'queue_header.setProperty("class", "section-header")'
    )
    content = content.replace(
        'line.setStyleSheet("background-color: #23232a; max-height: 1px;")',
        'line.setProperty("class", "divider-line")'
    )
    with open(f, 'w') as file:
        file.write(content)

    # 3. management_view.py
    f = 'frontend_desktop/views/components/management_view.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'name_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")',
        'name_label.setProperty("class", "manage-card-title")'
    )
    content = content.replace(
        'count_label.setStyleSheet("color: #9ca3af; font-size: 11px;")',
        'count_label.setProperty("class", "manage-card-count")'
    )
    content = content.replace(
        'empty.setStyleSheet("color: #9ca3af; font-size: 13px; padding: 20px;")',
        'empty.setProperty("class", "empty-state-text")'
    )
    with open(f, 'w') as file:
        file.write(content)

    # 4. game_grid.py
    f = 'frontend_desktop/views/components/game_grid.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'empty_label.setStyleSheet("color: #72757e; font-size: 14px; padding: 40px;")',
        'empty_label.setProperty("class", "empty-state-text")'
    )
    with open(f, 'w') as file:
        file.write(content)
        
    # 5. main_window.py
    f = 'frontend_desktop/views/main_window.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'self.view_title_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #ffffff;")',
        'self.view_title_label.setObjectName("viewTitle")'
    )
    with open(f, 'w') as file:
        file.write(content)
        
    # 6. settings_view.py
    f = 'frontend_desktop/views/components/settings_view.py'
    with open(f, 'r') as file:
        content = file.read()
    content = content.replace(
        'title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")',
        'title.setProperty("class", "view-title-large")'
    )
    content = content.replace(
        'size_group.setStyleSheet("QGroupBox { font-weight: bold; color: #a5b4fc; font-size: 14px; margin-top: 10px; padding-top: 15px; }")',
        'size_group.setProperty("class", "settings-group")'
    )
    content = content.replace(
        'sgdb_group.setStyleSheet("QGroupBox { font-weight: bold; color: #a5b4fc; font-size: 14px; margin-top: 10px; padding-top: 15px; }")',
        'sgdb_group.setProperty("class", "settings-group")'
    )
    content = content.replace(
        'about_group.setStyleSheet("QGroupBox { font-weight: bold; color: #a5b4fc; font-size: 14px; margin-top: 10px; padding-top: 15px; }")',
        'about_group.setProperty("class", "settings-group")'
    )
    content = content.replace(
        'sgdb_desc.setStyleSheet("color: #9ca3af; font-size: 12px;")',
        'sgdb_desc.setProperty("class", "settings-desc")'
    )
    content = content.replace(
        'info_label.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.6;")',
        'info_label.setProperty("class", "settings-desc")'
    )
    with open(f, 'w') as file:
        file.write(content)

    print("Refactoring completed.")

replace_inline_styles()

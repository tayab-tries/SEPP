import os

directory = r"d:\Bullshit\2.0\SE\EXAM\client\modules\examiner_dashboard"

replacements = {
    "client.modules.dashboard.dashboard_shell": "client.modules.examiner_dashboard.views.dashboard_shell",
    "client.modules.dashboard.examiner_alert_feed_section": "client.modules.examiner_dashboard.views.components.examiner_alert_feed_section",
    "client.modules.dashboard.examiner_exam_management_section": "client.modules.examiner_dashboard.views.components.examiner_exam_management_section",
    "client.modules.dashboard.examiner_metric_section": "client.modules.examiner_dashboard.views.components.examiner_metric_section",
    "client.modules.dashboard.examiner_overview_models": "client.modules.examiner_dashboard.scripts.examiner_overview_models",
    "client.modules.dashboard.examiner_overview_theme": "client.modules.examiner_dashboard.scripts.examiner_overview_theme",
    "client.modules.dashboard.settings": "client.modules.examiner_dashboard.settings",
    "client.modules.dashboard.exam_access_requests_view": "client.modules.examiner_dashboard.views.exam_access_requests_view",
    "client.modules.dashboard.class_view_examiner": "client.modules.examiner_dashboard.views.class_view_examiner",
    "client.modules.dashboard.exam_creation_view": "client.modules.examiner_dashboard.views.exam_creation_view",
    "client.modules.dashboard.examiner_exam_monitor_view": "client.modules.examiner_dashboard.views.examiner_exam_monitor_view",
    "client.modules.dashboard.examiner_overview": "client.modules.examiner_dashboard.views.examiner_overview",
    "client.modules.dashboard.examiner_dashboard": "client.modules.examiner_dashboard.examiner_dashboard_orchestrator"
}

for root, _, files in os.walk(directory):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            new_content = content
            for old, new in replacements.items():
                new_content = new_content.replace(old, new)
            
            if new_content != content:
                with open(path, "w", encoding="utf-8") as file:
                    file.write(new_content)
                print(f"Updated {path}")

# Fix main_window.py
main_window_path = r"d:\Bullshit\2.0\SE\EXAM\client\main_window.py"
with open(main_window_path, "r", encoding="utf-8") as file:
    content = file.read()
new_content = content
for old, new in replacements.items():
    new_content = new_content.replace(old, new)
if new_content != content:
    with open(main_window_path, "w", encoding="utf-8") as file:
        file.write(new_content)
    print(f"Updated {main_window_path}")

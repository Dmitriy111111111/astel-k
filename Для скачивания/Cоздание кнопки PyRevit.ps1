$base = "$env:APPDATA\pyRevit\Extensions\MyTools.extension\МоиКнопки.tab\Общие.panel\Привет.pushbutton"
New-Item -ItemType Directory -Force -Path $base | Out-Null

@'
from Autodesk.Revit.UI import TaskDialog
TaskDialog.Show("pyRevit","Привет! Кнопка работает.")
'@ | Set-Content "$base\script.py" -Encoding UTF8

@'
title: "Привет"
tooltip: "Пример кнопки pyRevit"
'@ | Set-Content "$base\bundle.yaml" -Encoding UTF8
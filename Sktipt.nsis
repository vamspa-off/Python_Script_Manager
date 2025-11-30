; Комментарии начинаются с точки с запятой
; Базовые настройки
Name "Мое Приложение"
OutFile "MyAppInstaller.exe"
InstallDir "$PROGRAMFILES\MyApp"

; Запрос прав администратора
RequestExecutionLevel admin

; Интерфейс
!include "MUI2.nsh"

; Настройки Modern UI
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Страницы установщика
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

; Страницы деинсталлятора
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; Языки
!insertmacro MUI_LANGUAGE "Russian"

; Секция установки
Section "MainSection" SEC01
  ; Установка файлов
  SetOutPath "$INSTDIR"
  File "MyApp.exe"
  File "README.txt"

  ; Создание подпапок
  SetOutPath "$INSTDIR\data"
  File /r "data\*.*"

  ; Создание ярлыков
  CreateShortcut "$DESKTOP\Мое Приложение.lnk" "$INSTDIR\MyApp.exe"
  CreateShortcut "$SMPROGRAMS\Мое Приложение.lnk" "$INSTDIR\MyApp.exe"

  ; Запись в реестр для удаления через Панель управления
  WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MyApp" \
    "DisplayName" "Мое Приложение"
  WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MyApp" \
    "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MyApp" \
    "DisplayIcon" "$INSTDIR\MyApp.exe"
  WriteRegStr HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MyApp" \
    "Publisher" "Моя Компания"

  ; Создание деинсталлятора
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

; Секция деинсталляции
Section "Uninstall"
  ; Удаление файлов
  Delete "$INSTDIR\MyApp.exe"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\uninstall.exe"
  RMDir /r "$INSTDIR\data"

  ; Удаление ярлыков
  Delete "$DESKTOP\Мое Приложение.lnk"
  Delete "$SMPROGRAMS\Мое Приложение.lnk"

  ; Удаление из реестра
  DeleteRegKey HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MyApp"

  ; Удаление папки, если пуста
  RMDir "$INSTDIR"
SectionEnd
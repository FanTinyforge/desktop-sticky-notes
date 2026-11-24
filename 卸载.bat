@echo off
chcp 65001 >nul
title 卸载桌面便利贴
echo.
echo   即将删除桌面便利贴的数据目录：
echo   %APPDATA%\StickyNotesTool
echo   其中包括全部便签、备份、日志和音效文件。
echo   程序本体 桌面便利贴.exe 需要你手动删除。
echo.
set /p yes=确认继续？输入 y 后回车：
if /i not "%yes%"=="y" goto cancel

taskkill /IM "桌面便利贴.exe" /F >nul 2>&1
rmdir /S /Q "%APPDATA%\StickyNotesTool" 2>nul
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\桌面便利贴.lnk" 2>nul
del "%USERPROFILE%\Desktop\桌面便利贴.lnk" 2>nul
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "StickyNotesTool" /f >nul 2>&1

echo.
echo   已清理便签数据和开机启动项。
echo   现在可以手动删除 桌面便利贴.exe 了。
pause
exit /b

:cancel
echo.
echo   已取消，什么都没有删除。
pause

@echo off
del /S /Q .git\desktop.ini
del /S /Q .git\refs\desktop.ini
del /S /Q .git\logs\desktop.ini
echo Limpeza concluida!
git pull --tags origin master
pause
"""
Script auxiliar para gerar o executável standalone da aplicação.

Uso (na pasta do projeto, com as dependências instaladas):
    python build_exe.py

No Windows, gera "dist/GestaoProjetos.exe".
No Linux/Mac, gera "dist/GestaoProjetos".

Nota: o executável deve ser gerado no mesmo sistema operativo onde vai
ser usado (um .exe para Windows tem de ser criado num Windows).
"""
import PyInstaller.__main__

PyInstaller.__main__.run([
    "main.py",
    "--name=GestaoProjetos",
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--icon=assets/icon.ico",
])

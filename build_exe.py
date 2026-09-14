"""
Script auxiliar para gerar o executável standalone da aplicação.

Uso (na pasta do projeto, com as dependências instaladas):
    python build_exe.py

Gera "dist/GestaoProjetos/" — uma pasta com o GestaoProjetos.exe (Windows)
ou GestaoProjetos (Linux/Mac) e os respetivos ficheiros de suporte.

Nota: o executável deve ser gerado no mesmo sistema operativo onde vai
ser usado (um .exe para Windows tem de ser criado num Windows).

Porque "--onedir" em vez de "--onefile" e "--noupx":
Um ficheiro único que se auto-extrai para uma pasta temporária ao arrancar
(--onefile) e a compressão UPX são dois padrões que os antivírus associam
a malware, mesmo quando o conteúdo é inofensivo. Usar uma pasta normal
(--onedir), sem compressão UPX, e incluir metadados de versão reduz
bastante a probabilidade de o Windows/antivírus assinalarem falsamente
o executável como suspeito.
"""
import PyInstaller.__main__
from sync_versao import sincronizar_version_info, sincronizar_installer_iss

sincronizar_version_info()
sincronizar_installer_iss()

PyInstaller.__main__.run([
    "main.py",
    "--name=GestaoProjetos",
    "--onedir",
    "--windowed",
    "--noconfirm",
    "--noupx",
    "--icon=assets/icon.ico",
    "--version-file=version_info.txt",
])

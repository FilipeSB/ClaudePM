"""
Sincroniza a versão da aplicação (definida em utils/versao.py) para os
ficheiros usados no build: version_info.txt (metadados do .exe) e
installer.iss (instalador Inno Setup).

Uso: python sync_versao.py
Corre automaticamente sempre que fores gerar um build (build_exe.py chama
este script antes de compilar), por isso normalmente não precisas de o
correr manualmente -- mas podes, para confirmar a versão atual.
"""
import re
from utils.versao import VERSAO


def _versao_4_partes(v: str) -> str:
    """'1.2.0' -> '1, 2, 0, 0' (formato exigido pelo FixedFileInfo do PyInstaller)."""
    partes = v.split(".")
    while len(partes) < 4:
        partes.append("0")
    return ", ".join(partes[:4])


def sincronizar_version_info():
    caminho = "version_info.txt"
    with open(caminho, encoding="utf-8") as f:
        conteudo = f.read()

    conteudo = re.sub(r"filevers=\([^)]*\)", f"filevers=({_versao_4_partes(VERSAO)})", conteudo)
    conteudo = re.sub(r"prodvers=\([^)]*\)", f"prodvers=({_versao_4_partes(VERSAO)})", conteudo)
    conteudo = re.sub(
        r"StringStruct\(u'FileVersion', u'[^']*'\)",
        f"StringStruct(u'FileVersion', u'{VERSAO}.0')", conteudo,
    )
    conteudo = re.sub(
        r"StringStruct\(u'ProductVersion', u'[^']*'\)",
        f"StringStruct(u'ProductVersion', u'{VERSAO}.0')", conteudo,
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    print(f"version_info.txt atualizado para {VERSAO}")


def sincronizar_installer_iss():
    caminho = "installer.iss"
    with open(caminho, encoding="utf-8") as f:
        conteudo = f.read()

    conteudo = re.sub(
        r'#define MyAppVersion "[^"]*"',
        f'#define MyAppVersion "{VERSAO}"', conteudo,
    )

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    print(f"installer.iss atualizado para {VERSAO}")


if __name__ == "__main__":
    sincronizar_version_info()
    sincronizar_installer_iss()

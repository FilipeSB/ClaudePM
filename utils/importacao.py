"""
Geração de template Excel / exportação dos dados atuais, e importação a
partir de qualquer um dos dois.

O TEMPLATE (em branco, com exemplos) não tem coluna de ID -- destina-se a
introduzir dados novos, e as referências entre entidades (ex: Pessoa ->
Equipa) são feitas por NOME ou CÓDIGO, para ser fácil de preencher à mão.

A EXPORTAÇÃO DE DADOS ATUAIS tem sempre uma coluna "ID" em primeiro lugar,
para permitir voltar a importar o ficheiro depois de o editar/completar e
atualizar exatamente os registos certos (mesmo que o nome tenha mudado).

Na importação, para cada linha: se a coluna ID tiver um valor e esse ID
existir na base de dados, o registo é atualizado diretamente por ID; caso
contrário (sem ID, ou ID vazio -- ex: uma linha nova acrescentada ao
ficheiro exportado), procura-se/cria-se pelo nome ou código, como no
template em branco.

Ordem de importação (respeitando dependências): Clientes, Equipas, Perfis,
Pessoas, Projetos, Tarefas, Alocacoes.
"""
from datetime import datetime, date
from utils.cores import cor_valida
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from database.models import (
    Cliente, Equipa, Perfil, Pessoa, Projeto, Tarefa, Alocacao,
    TIPOS_ALOCACAO,
)

# Colunas do TEMPLATE em branco (sem ID)
FOLHAS = {
    "Clientes": ["Nome", "Contacto", "Ativo (Sim/Não)"],
    "Equipas": ["Nome", "Descrição"],
    "Perfis": ["Código (CC01-CC07)", "Designação", "Custo/Hora", "Custo/Dia"],
    "Pessoas": ["Nome", "Equipa (nome)", "Perfil (código)", "Email", "Ativo (Sim/Não)", "Cor (#RRGGBB, opcional)"],
    "Projetos": ["Nome", "Cliente (nome)", "Data Início (AAAA-MM-DD)", "Data Fim (AAAA-MM-DD)",
                 "Objetivos", "Estado"],
    "Tarefas": ["Nome", "Projeto (nome)", "Data Início (AAAA-MM-DD)", "Data Fim (AAAA-MM-DD)", "Estado"],
    "Alocacoes": ["Tarefa (nome)", "Projeto (nome)", "Pessoa (nome)", "Tipo (percentagem/horas)",
                  "Percentagem (0-100)", "Horas (opcional)"],
}

EXEMPLOS = {
    "Clientes": [["Acme Lda", "geral@acme.pt", "Sim"]],
    "Equipas": [["Equipa Dev", "Equipa de desenvolvimento de software"]],
    "Perfis": [],  # os perfis já vêm pré-criados na aplicação (CC01-CC07)
    "Pessoas": [["Ana Silva", "Equipa Dev", "CC04", "ana@acme.pt", "Sim"]],
    "Projetos": [["Portal Cliente", "Acme Lda", "2026-01-01", "2026-06-30",
                  "Criar portal para clientes", "Em curso"]],
    "Tarefas": [["Desenvolver login", "Portal Cliente", "2026-01-05", "2026-01-20", "Em curso"]],
    "Alocacoes": [["Desenvolver login", "Portal Cliente", "Ana Silva", "percentagem", "70", "", "8h_uteis"]],
}


def _escrever_folha(wb, nome_folha, colunas, linhas):
    ws = wb.create_sheet(nome_folha)
    ws.append(colunas)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2F5496")
    for linha in linhas:
        ws.append(linha)
    for col_cells in ws.columns:
        largura = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells) + 2
        ws.column_dimensions[col_cells[0].column_letter].width = min(max(largura, 14), 45)


def gerar_template(caminho: str):
    """Gera o template em branco (sem ID), com um exemplo por folha."""
    wb = Workbook()
    wb.remove(wb.active)

    for nome_folha, colunas in FOLHAS.items():
        _escrever_folha(wb, nome_folha, colunas, EXEMPLOS.get(nome_folha, []))

    ws_info = wb.create_sheet("Instruções", 0)
    instrucoes = [
        "Instruções de preenchimento",
        "",
        "1. Preenche uma linha por registo em cada folha (não apagues os cabeçalhos).",
        "2. As colunas com '(nome)' ou '(código)' referem-se a registos de outra folha:",
        "   escreve exatamente o mesmo nome/código já usado nessa folha.",
        "3. Datas no formato AAAA-MM-DD (ex: 2026-01-31).",
        "4. Na folha 'Alocacoes', preenche OU 'Percentagem' OU 'Horas' (não ambos):",
        "   - Tipo 'percentagem': preenche a coluna Percentagem (0 a 100).",
        "   - Tipo 'horas': preenche a coluna Horas; a percentagem é calculada",
        "     automaticamente (8 horas = 100%, só em dias úteis).",
        "6. Podes importar este ficheiro em: menu Ficheiro > Importar dados de Excel.",
        "7. Registos com o mesmo nome/código de um já existente são ATUALIZADOS, não duplicados.",
    ]
    for linha in instrucoes:
        ws_info.append([linha])
    ws_info["A1"].font = Font(bold=True, size=14)
    ws_info.column_dimensions["A"].width = 90

    wb.save(caminho)


def exportar_dados_atuais(caminho: str, session):
    """
    Exporta TODOS os dados atuais da base de dados para Excel, uma folha
    por entidade, com uma coluna "ID" em primeiro lugar em cada folha
    (para permitir voltar a importar o ficheiro e atualizar exatamente os
    registos certos). Pode ser reaberto, editado (incluindo acrescentar
    linhas novas, sem ID) e reimportado.
    """
    wb = Workbook()
    wb.remove(wb.active)

    clientes = session.query(Cliente).order_by(Cliente.id).all()
    _escrever_folha(wb, "Clientes", ["ID"] + FOLHAS["Clientes"], [
        [c.id, c.nome, c.contacto or "", "Sim" if c.ativo else "Não"] for c in clientes
    ])

    equipas = session.query(Equipa).order_by(Equipa.id).all()
    _escrever_folha(wb, "Equipas", ["ID"] + FOLHAS["Equipas"], [
        [e.id, e.nome, e.descricao or ""] for e in equipas
    ])

    perfis = session.query(Perfil).order_by(Perfil.id).all()
    _escrever_folha(wb, "Perfis", ["ID"] + FOLHAS["Perfis"], [
        [p.id, p.codigo, p.designacao or "", float(p.custo_hora or 0), float(p.custo_dia or 0)] for p in perfis
    ])

    pessoas = session.query(Pessoa).order_by(Pessoa.id).all()
    _escrever_folha(wb, "Pessoas", ["ID"] + FOLHAS["Pessoas"], [
        [p.id, p.nome, p.equipa.nome if p.equipa else "", p.perfil.codigo if p.perfil else "",
         p.email or "", "Sim" if p.ativo else "Não", p.cor or ""]
        for p in pessoas
    ])

    projetos = session.query(Projeto).order_by(Projeto.id).all()
    _escrever_folha(wb, "Projetos", ["ID"] + FOLHAS["Projetos"], [
        [p.id, p.nome, p.cliente.nome if p.cliente else "",
         str(p.data_inicio) if p.data_inicio else "", str(p.data_fim) if p.data_fim else "",
         p.objetivos or "", p.estado]
        for p in projetos
    ])

    tarefas = session.query(Tarefa).order_by(Tarefa.id).all()
    _escrever_folha(wb, "Tarefas", ["ID"] + FOLHAS["Tarefas"], [
        [t.id, t.nome, t.projeto.nome if t.projeto else "",
         str(t.data_inicio) if t.data_inicio else "", str(t.data_fim) if t.data_fim else "",
         t.estado]
        for t in tarefas
    ])

    alocacoes = session.query(Alocacao).order_by(Alocacao.id).all()
    _escrever_folha(wb, "Alocacoes", ["ID"] + FOLHAS["Alocacoes"], [
        [a.id, a.tarefa.nome if a.tarefa else "", (a.tarefa.projeto.nome if a.tarefa and a.tarefa.projeto else ""),
         a.pessoa.nome if a.pessoa else "", a.tipo or "percentagem",
         float(a.percentagem or 0), float(a.horas) if a.horas is not None else ""]
        for a in alocacoes
    ])

    ws_info = wb.create_sheet("Instruções", 0)
    instrucoes = [
        "Exportação de dados atuais",
        "",
        "Este ficheiro contém todos os dados atualmente na aplicação, um "
        "registo por linha, com uma coluna 'ID' em cada folha.",
        "",
        "Para editar dados existentes: muda os valores nas colunas dessa "
        "linha, mantendo o ID -- ao reimportar, esse registo é atualizado.",
        "Para acrescentar registos novos: adiciona uma linha nova e deixa "
        "a coluna ID em branco -- será criado um registo novo.",
        "Para remover um registo: apaga-o diretamente na aplicação (a "
        "importação nunca apaga registos, mesmo que a linha seja removida "
        "do ficheiro).",
        "",
        "Reimporta este ficheiro em: menu Ficheiro > Importar dados de Excel.",
        "",
        "IMPORTANTE: as colunas que referenciam outra folha (ex: 'Cliente "
        "(nome)' na folha Projetos) continuam a ser por NOME/CÓDIGO, não "
        "por ID. Se renomeares um cliente nesta folha, atualiza também o "
        "nome nas outras folhas que o referenciam -- caso contrário essa "
        "referência deixa de ser encontrada ao reimportar.",
    ]
    for linha in instrucoes:
        ws_info.append([linha])
    ws_info["A1"].font = Font(bold=True, size=14)
    ws_info.column_dimensions["A"].width = 90

    wb.save(caminho)


# ---------------------------------------------------------------------------
def _valor(row, idx, default=None):
    if idx >= len(row):
        return default
    v = row[idx]
    return default if v is None else v


def _bool_pt(valor, default=True):
    if valor is None or valor == "":
        return default
    return str(valor).strip().lower() in ("sim", "yes", "true", "1")


def _data(valor):
    if not valor:
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.strptime(str(valor).strip(), "%Y-%m-%d").date()


def _tem_coluna_id(ws) -> bool:
    primeiro_cabecalho = ws.cell(row=1, column=1).value
    return bool(primeiro_cabecalho) and str(primeiro_cabecalho).strip().upper() == "ID"


def _ler_linhas(ws):
    """
    Devolve lista de (id_valor_ou_None, linha_de_dados_sem_a_coluna_id).
    Se a folha não tiver coluna ID, id_valor é sempre None.
    """
    tem_id = _tem_coluna_id(ws)
    linhas_cruas = list(ws.iter_rows(min_row=2, values_only=True))
    resultado = []
    for linha in linhas_cruas:
        if not any(v not in (None, "") for v in linha):
            continue
        if tem_id:
            resultado.append((linha[0], linha[1:]))
        else:
            resultado.append((None, linha))
    return resultado


def _obter_registo(session, Modelo, id_valor, **filtro_natural):
    """
    Se id_valor for válido e existir, devolve esse registo (ignorando o
    filtro natural -- o ID manda). Caso contrário, procura pelo filtro
    natural (nome/código) e cria um registo novo se não existir.
    Garante que o registo devolvido já está na sessão (session.add, se novo).
    """
    if id_valor not in (None, ""):
        try:
            registo = session.get(Modelo, int(id_valor))
            if registo:
                return registo
        except (TypeError, ValueError):
            pass

    registo = session.query(Modelo).filter_by(**filtro_natural).first()
    if registo is None:
        registo = Modelo(**filtro_natural)
        session.add(registo)
    return registo


def importar_excel(caminho: str, session):
    """
    Lê o ficheiro Excel (template em branco OU exportação de dados atuais,
    com coluna ID) e cria/atualiza registos na base de dados.
    Retorna um dicionário-resumo: {"Clientes": 3, "Equipas": 1, ...}, e uma
    lista de avisos (strings) para linhas que não puderam ser importadas.
    """
    from utils.calculos import horas_para_percentagem

    wb = load_workbook(caminho, data_only=True)
    resumo = {chave: 0 for chave in FOLHAS}
    avisos = []

    # --- Clientes ---
    if "Clientes" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Clientes"]):
            nome = _valor(linha, 0)
            if not nome and id_valor in (None, ""):
                continue
            cliente = _obter_registo(session, Cliente, id_valor, nome=nome)
            if nome:
                cliente.nome = nome
            cliente.contacto = _valor(linha, 1, "")
            cliente.ativo = _bool_pt(_valor(linha, 2), True)
            resumo["Clientes"] += 1
        session.flush()

    # --- Equipas ---
    if "Equipas" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Equipas"]):
            nome = _valor(linha, 0)
            if not nome and id_valor in (None, ""):
                continue
            equipa = _obter_registo(session, Equipa, id_valor, nome=nome)
            if nome:
                equipa.nome = nome
            equipa.descricao = _valor(linha, 1, "")
            resumo["Equipas"] += 1
        session.flush()

    # --- Perfis ---
    if "Perfis" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Perfis"]):
            codigo = _valor(linha, 0)
            if not codigo and id_valor in (None, ""):
                continue
            codigo = str(codigo).strip().upper() if codigo else None
            perfil = _obter_registo(session, Perfil, id_valor, codigo=codigo)
            if codigo:
                perfil.codigo = codigo
            perfil.designacao = _valor(linha, 1, "")
            perfil.custo_hora = _valor(linha, 2, 0) or 0
            perfil.custo_dia = _valor(linha, 3, 0) or 0
            resumo["Perfis"] += 1
        session.flush()

    # --- Pessoas ---
    if "Pessoas" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Pessoas"]):
            nome = _valor(linha, 0)
            if not nome and id_valor in (None, ""):
                continue
            equipa_nome = _valor(linha, 1)
            perfil_codigo = _valor(linha, 2)
            equipa = session.query(Equipa).filter_by(nome=equipa_nome).first() if equipa_nome else None
            perfil = session.query(Perfil).filter_by(codigo=str(perfil_codigo).strip().upper()).first() if perfil_codigo else None
            if equipa_nome and not equipa:
                avisos.append(f"Pessoas: equipa '{equipa_nome}' não encontrada para '{nome}'.")
            if perfil_codigo and not perfil:
                avisos.append(f"Pessoas: perfil '{perfil_codigo}' não encontrado para '{nome}'.")

            pessoa = _obter_registo(session, Pessoa, id_valor, nome=nome)
            if nome:
                pessoa.nome = nome
            pessoa.equipa_id = equipa.id if equipa else None
            pessoa.perfil_id = perfil.id if perfil else None
            pessoa.email = _valor(linha, 3, "")
            pessoa.ativo = _bool_pt(_valor(linha, 4), True)
            cor = _valor(linha, 5)
            if cor and cor_valida(str(cor).strip()):
                pessoa.cor = str(cor).strip().upper()
            resumo["Pessoas"] += 1
        session.flush()

    # --- Projetos ---
    if "Projetos" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Projetos"]):
            nome = _valor(linha, 0)
            if not nome and id_valor in (None, ""):
                continue
            cliente_nome = _valor(linha, 1)
            cliente = session.query(Cliente).filter_by(nome=cliente_nome).first() if cliente_nome else None
            if cliente_nome and not cliente:
                avisos.append(f"Projetos: cliente '{cliente_nome}' não encontrado para '{nome}'.")

            projeto = _obter_registo(session, Projeto, id_valor, nome=nome)
            if nome:
                projeto.nome = nome
            projeto.cliente_id = cliente.id if cliente else None
            try:
                projeto.data_inicio = _data(_valor(linha, 2))
                projeto.data_fim = _data(_valor(linha, 3))
            except ValueError:
                avisos.append(f"Projetos: datas inválidas em '{nome}' (usar AAAA-MM-DD).")
            projeto.objetivos = _valor(linha, 4, "")
            estado = _valor(linha, 5, "Planeado")
            if estado:
                projeto.estado = estado
            resumo["Projetos"] += 1
        session.flush()

    # --- Tarefas ---
    if "Tarefas" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Tarefas"]):
            nome = _valor(linha, 0)
            if not nome and id_valor in (None, ""):
                continue
            projeto_nome = _valor(linha, 1)
            projeto = session.query(Projeto).filter_by(nome=projeto_nome).first() if projeto_nome else None
            if projeto_nome and not projeto:
                avisos.append(f"Tarefas: projeto '{projeto_nome}' não encontrado para '{nome}'.")

            if id_valor not in (None, ""):
                tarefa = _obter_registo(session, Tarefa, id_valor, nome=nome)
            else:
                tarefa = (
                    session.query(Tarefa)
                    .filter_by(nome=nome, projeto_id=projeto.id if projeto else None)
                    .first()
                )
                if not tarefa:
                    tarefa = Tarefa(nome=nome)
                    session.add(tarefa)
            if nome:
                tarefa.nome = nome
            tarefa.projeto_id = projeto.id if projeto else None
            try:
                tarefa.data_inicio = _data(_valor(linha, 2))
                tarefa.data_fim = _data(_valor(linha, 3))
            except ValueError:
                avisos.append(f"Tarefas: datas inválidas em '{nome}' (usar AAAA-MM-DD).")
            estado = _valor(linha, 4, "Não iniciada")
            if estado:
                tarefa.estado = estado
            resumo["Tarefas"] += 1
        session.flush()

    # --- Alocacoes ---
    if "Alocacoes" in wb.sheetnames:
        for id_valor, linha in _ler_linhas(wb["Alocacoes"]):
            tarefa_nome = _valor(linha, 0)
            projeto_nome = _valor(linha, 1)
            pessoa_nome = _valor(linha, 2)
            if not tarefa_nome and not pessoa_nome and id_valor in (None, ""):
                continue

            projeto = session.query(Projeto).filter_by(nome=projeto_nome).first() if projeto_nome else None
            query_tarefa = session.query(Tarefa).filter_by(nome=tarefa_nome)
            if projeto:
                query_tarefa = query_tarefa.filter_by(projeto_id=projeto.id)
            tarefa = query_tarefa.first()
            pessoa = session.query(Pessoa).filter_by(nome=pessoa_nome).first()

            if id_valor in (None, "") and not tarefa:
                avisos.append(f"Alocacoes: tarefa '{tarefa_nome}' não encontrada.")
                continue
            if id_valor in (None, "") and not pessoa:
                avisos.append(f"Alocacoes: pessoa '{pessoa_nome}' não encontrada.")
                continue

            tipo = str(_valor(linha, 3, "percentagem") or "percentagem").strip().lower()
            tipo = tipo if tipo in TIPOS_ALOCACAO else "percentagem"
            if tipo == "horas":
                horas = float(_valor(linha, 5, 0) or 0)
                percentagem = horas_para_percentagem(horas)
            else:
                horas = None
                percentagem = float(_valor(linha, 4, 0) or 0)

            if id_valor not in (None, ""):
                try:
                    alocacao = session.get(Alocacao, int(id_valor))
                except (TypeError, ValueError):
                    alocacao = None
                if not alocacao:
                    avisos.append(f"Alocacoes: ID {id_valor} não encontrado -- linha ignorada.")
                    continue
            else:
                alocacao = (
                    session.query(Alocacao)
                    .filter_by(tarefa_id=tarefa.id, pessoa_id=pessoa.id)
                    .first()
                )
                if not alocacao:
                    alocacao = Alocacao(tarefa_id=tarefa.id, pessoa_id=pessoa.id)
                    session.add(alocacao)

            if tarefa:
                alocacao.tarefa_id = tarefa.id
            if pessoa:
                alocacao.pessoa_id = pessoa.id
            alocacao.tipo = tipo
            alocacao.horas = horas
            alocacao.percentagem = percentagem
            resumo["Alocacoes"] += 1
        session.flush()

    session.commit()
    return resumo, avisos

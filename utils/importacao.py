"""
Geração de template Excel e importação de dados a partir dele.

O template tem uma folha por entidade. As referências entre entidades
(ex: Pessoa -> Equipa) são feitas por NOME (ou código, no caso do Perfil),
não por ID, para ser fácil de preencher à mão.

Ordem de importação (respeitando dependências): Clientes, Equipas, Perfis,
Pessoas, Projetos, Tarefas, Alocacoes.
"""
from datetime import datetime, date
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from database.models import (
    Cliente, Equipa, Perfil, Pessoa, Projeto, Tarefa, Alocacao,
    ESTADOS_PROJETO, ESTADOS_TAREFA, TIPOS_ALOCACAO, CATEGORIAS_ALOCACAO,
)

FOLHAS = {
    "Clientes": ["Nome", "Contacto", "Ativo (Sim/Não)"],
    "Equipas": ["Nome", "Descrição"],
    "Perfis": ["Código (CC01-CC07)", "Designação", "Custo/Hora", "Custo/Dia"],
    "Pessoas": ["Nome", "Equipa (nome)", "Perfil (código)", "Email", "Ativo (Sim/Não)"],
    "Projetos": ["Nome", "Cliente (nome)", "Data Início (AAAA-MM-DD)", "Data Fim (AAAA-MM-DD)",
                 "Objetivos", "Estado"],
    "Tarefas": ["Nome", "Projeto (nome)", "Data Início (AAAA-MM-DD)", "Data Fim (AAAA-MM-DD)", "Estado"],
    "Alocacoes": ["Tarefa (nome)", "Projeto (nome)", "Pessoa (nome)", "Tipo (percentagem/horas)",
                  "Percentagem (0-100)", "Horas", "Categoria (8h_uteis/24h_todos)"],
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


def gerar_template(caminho: str):
    wb = Workbook()
    wb.remove(wb.active)

    for nome_folha, colunas in FOLHAS.items():
        ws = wb.create_sheet(nome_folha)
        ws.append(colunas)
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2F5496")
        for linha in EXEMPLOS.get(nome_folha, []):
            ws.append(linha)
        for col_cells in ws.columns:
            largura = max((len(str(c.value)) if c.value is not None else 0) for c in col_cells) + 2
            ws.column_dimensions[col_cells[0].column_letter].width = min(max(largura, 14), 45)

    # Folha de instruções, colocada em primeiro lugar
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
        "     automaticamente a partir da Categoria escolhida.",
        "5. Categoria: '8h_uteis' (8 horas em dias úteis) ou '24h_todos' (24h todos os dias).",
        f"6. Estados possíveis para Projetos: {', '.join(ESTADOS_PROJETO)}",
        f"7. Estados possíveis para Tarefas: {', '.join(ESTADOS_TAREFA)}",
        "8. Podes importar este ficheiro em: menu Ficheiro > Importar dados de Excel.",
        "9. Registos com o mesmo nome/código de um já existente são ATUALIZADOS,",
        "   não duplicados.",
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


def _ler_linhas(ws):
    linhas = list(ws.iter_rows(min_row=2, values_only=True))
    return [linha for linha in linhas if any(v not in (None, "") for v in linha)]


def importar_excel(caminho: str, session):
    """
    Lê o ficheiro Excel e cria/atualiza registos na base de dados.
    Retorna um dicionário-resumo: {"Clientes": 3, "Equipas": 1, ...}, e uma
    lista de avisos (strings) para linhas que não puderam ser importadas.
    """
    from utils.calculos import horas_para_percentagem

    wb = load_workbook(caminho, data_only=True)
    resumo = {chave: 0 for chave in FOLHAS}
    avisos = []

    # --- Clientes ---
    if "Clientes" in wb.sheetnames:
        for linha in _ler_linhas(wb["Clientes"]):
            nome = _valor(linha, 0)
            if not nome:
                continue
            cliente = session.query(Cliente).filter_by(nome=nome).first()
            if not cliente:
                cliente = Cliente(nome=nome)
                session.add(cliente)
            cliente.contacto = _valor(linha, 1, "")
            cliente.ativo = _bool_pt(_valor(linha, 2), True)
            resumo["Clientes"] += 1
        session.flush()

    # --- Equipas ---
    if "Equipas" in wb.sheetnames:
        for linha in _ler_linhas(wb["Equipas"]):
            nome = _valor(linha, 0)
            if not nome:
                continue
            equipa = session.query(Equipa).filter_by(nome=nome).first()
            if not equipa:
                equipa = Equipa(nome=nome)
                session.add(equipa)
            equipa.descricao = _valor(linha, 1, "")
            resumo["Equipas"] += 1
        session.flush()

    # --- Perfis ---
    if "Perfis" in wb.sheetnames:
        for linha in _ler_linhas(wb["Perfis"]):
            codigo = _valor(linha, 0)
            if not codigo:
                continue
            codigo = str(codigo).strip().upper()
            perfil = session.query(Perfil).filter_by(codigo=codigo).first()
            if not perfil:
                perfil = Perfil(codigo=codigo)
                session.add(perfil)
            perfil.designacao = _valor(linha, 1, "")
            perfil.custo_hora = _valor(linha, 2, 0) or 0
            perfil.custo_dia = _valor(linha, 3, 0) or 0
            resumo["Perfis"] += 1
        session.flush()

    # --- Pessoas ---
    if "Pessoas" in wb.sheetnames:
        for linha in _ler_linhas(wb["Pessoas"]):
            nome = _valor(linha, 0)
            if not nome:
                continue
            equipa_nome = _valor(linha, 1)
            perfil_codigo = _valor(linha, 2)
            equipa = session.query(Equipa).filter_by(nome=equipa_nome).first() if equipa_nome else None
            perfil = session.query(Perfil).filter_by(codigo=str(perfil_codigo).strip().upper()).first() if perfil_codigo else None
            if equipa_nome and not equipa:
                avisos.append(f"Pessoas: equipa '{equipa_nome}' não encontrada para '{nome}'.")
            if perfil_codigo and not perfil:
                avisos.append(f"Pessoas: perfil '{perfil_codigo}' não encontrado para '{nome}'.")

            pessoa = session.query(Pessoa).filter_by(nome=nome).first()
            if not pessoa:
                pessoa = Pessoa(nome=nome)
                session.add(pessoa)
            pessoa.equipa_id = equipa.id if equipa else None
            pessoa.perfil_id = perfil.id if perfil else None
            pessoa.email = _valor(linha, 3, "")
            pessoa.ativo = _bool_pt(_valor(linha, 4), True)
            resumo["Pessoas"] += 1
        session.flush()

    # --- Projetos ---
    if "Projetos" in wb.sheetnames:
        for linha in _ler_linhas(wb["Projetos"]):
            nome = _valor(linha, 0)
            if not nome:
                continue
            cliente_nome = _valor(linha, 1)
            cliente = session.query(Cliente).filter_by(nome=cliente_nome).first() if cliente_nome else None
            if cliente_nome and not cliente:
                avisos.append(f"Projetos: cliente '{cliente_nome}' não encontrado para '{nome}'.")

            projeto = session.query(Projeto).filter_by(nome=nome).first()
            if not projeto:
                projeto = Projeto(nome=nome)
                session.add(projeto)
            projeto.cliente_id = cliente.id if cliente else None
            try:
                projeto.data_inicio = _data(_valor(linha, 2))
                projeto.data_fim = _data(_valor(linha, 3))
            except ValueError:
                avisos.append(f"Projetos: datas inválidas em '{nome}' (usar AAAA-MM-DD).")
            projeto.objetivos = _valor(linha, 4, "")
            estado = _valor(linha, 5, "Planeado")
            projeto.estado = estado if estado in ESTADOS_PROJETO else "Planeado"
            resumo["Projetos"] += 1
        session.flush()

    # --- Tarefas ---
    if "Tarefas" in wb.sheetnames:
        for linha in _ler_linhas(wb["Tarefas"]):
            nome = _valor(linha, 0)
            if not nome:
                continue
            projeto_nome = _valor(linha, 1)
            projeto = session.query(Projeto).filter_by(nome=projeto_nome).first() if projeto_nome else None
            if projeto_nome and not projeto:
                avisos.append(f"Tarefas: projeto '{projeto_nome}' não encontrado para '{nome}'.")

            tarefa = (
                session.query(Tarefa)
                .filter_by(nome=nome, projeto_id=projeto.id if projeto else None)
                .first()
            )
            if not tarefa:
                tarefa = Tarefa(nome=nome)
                session.add(tarefa)
            tarefa.projeto_id = projeto.id if projeto else None
            try:
                tarefa.data_inicio = _data(_valor(linha, 2))
                tarefa.data_fim = _data(_valor(linha, 3))
            except ValueError:
                avisos.append(f"Tarefas: datas inválidas em '{nome}' (usar AAAA-MM-DD).")
            estado = _valor(linha, 4, "Não iniciada")
            tarefa.estado = estado if estado in ESTADOS_TAREFA else "Não iniciada"
            resumo["Tarefas"] += 1
        session.flush()

    # --- Alocacoes ---
    if "Alocacoes" in wb.sheetnames:
        for linha in _ler_linhas(wb["Alocacoes"]):
            tarefa_nome = _valor(linha, 0)
            projeto_nome = _valor(linha, 1)
            pessoa_nome = _valor(linha, 2)
            if not tarefa_nome or not pessoa_nome:
                continue

            projeto = session.query(Projeto).filter_by(nome=projeto_nome).first() if projeto_nome else None
            query_tarefa = session.query(Tarefa).filter_by(nome=tarefa_nome)
            if projeto:
                query_tarefa = query_tarefa.filter_by(projeto_id=projeto.id)
            tarefa = query_tarefa.first()
            pessoa = session.query(Pessoa).filter_by(nome=pessoa_nome).first()

            if not tarefa:
                avisos.append(f"Alocacoes: tarefa '{tarefa_nome}' não encontrada.")
                continue
            if not pessoa:
                avisos.append(f"Alocacoes: pessoa '{pessoa_nome}' não encontrada.")
                continue

            tipo = str(_valor(linha, 3, "percentagem") or "percentagem").strip().lower()
            tipo = tipo if tipo in TIPOS_ALOCACAO else "percentagem"
            categoria = str(_valor(linha, 6, "8h_uteis") or "8h_uteis").strip()
            categoria = categoria if categoria in CATEGORIAS_ALOCACAO else "8h_uteis"

            if tipo == "horas":
                horas = float(_valor(linha, 5, 0) or 0)
                percentagem = horas_para_percentagem(horas, categoria)
            else:
                horas = None
                percentagem = float(_valor(linha, 4, 0) or 0)

            alocacao = (
                session.query(Alocacao)
                .filter_by(tarefa_id=tarefa.id, pessoa_id=pessoa.id)
                .first()
            )
            if not alocacao:
                alocacao = Alocacao(tarefa_id=tarefa.id, pessoa_id=pessoa.id)
                session.add(alocacao)
            alocacao.tipo = tipo
            alocacao.horas = horas
            alocacao.categoria = categoria
            alocacao.percentagem = percentagem
            resumo["Alocacoes"] += 1
        session.flush()

    session.commit()
    return resumo, avisos

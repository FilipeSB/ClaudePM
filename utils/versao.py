"""
Versão da aplicação — fonte única de verdade.

Esquema de versionamento semântico (MAJOR.MINOR.PATCH):
  - MAJOR: mudanças estruturais grandes (ex: redesenho do calendário,
    alterações que quebram compatibilidade com dados/instalações antigas).
  - MINOR: novas funcionalidades (ex: nova vista, novo tipo de filtro,
    nova exportação).
  - PATCH: correções de bugs, pequenos ajustes, sem funcionalidade nova.

Este número é atualizado a cada ronda de alterações pedidas, e é o mesmo
valor usado no título da janela principal, no instalador (installer.iss)
e nos metadados do executável (version_info.txt) -- os três devem ser
mantidos em sincronia manualmente sempre que a versão mudar aqui.
"""

VERSAO = "1.5.0"

# Histórico resumido de versões (mais recente primeiro), para referência.
HISTORICO_VERSOES = [
    ("1.5.0", "Feriados (Configuracoes > Feriados) com importacao automatica da "
               "internet, marcados no calendario; cor por pessoa usada nas barras "
               "do calendario e da alocacao (barras proporcionais); alocacao sempre "
               "em dias uteis de 8h (categoria removida; conversao horas/percentagem "
               "imediata); atividades com Cliente -> Projeto em cascata e filtros por "
               "cliente/projeto; filtro por cliente em projetos; duplo clique abre "
               "a edicao em todas as listagens; calendario: trocar pessoa, escolher "
               "horas ou percentagem, fins de semana/feriados sombreados; menu Ajuda "
               "mais a direita; ao selecionar um estado, o nome aparece para editar."),
    ("1.4.0", "Correcao de fecho inesperado ao editar atividades (dialogo passa a "
               "usar apenas dados simples, nunca objetos ligados a sessoes fechadas "
               "da base de dados); percentagens com 1 casa decimal e sem coluna de "
               "ID em todos os ecrans; eliminacao de registos do historico de custos "
               "de perfis (com minimo obrigatorio de 1); calculo de custo do projeto "
               "corrigido para refletir corretamente o historico de custos por data; "
               "atividades mostram o cliente do projeto (na listagem e ao escolher "
               "projeto); calendario com colunas ordenaveis, cliques que abrem os "
               "registos (cliente/projeto/atividade/pessoa) e edicao direta do "
               "estado e da percentagem de alocacao; alocacao com colunas ordenaveis."),
    ("1.3.0", "Exportação de todos os dados atuais para Excel (com coluna de ID, "
               "para reimportação por ID); gestão de estados configuráveis de "
               "Projetos e Atividades (menu Configurações); ordenação por "
               "qualquer coluna em todas as listagens; correção de bug nos "
               "custos por data de vigência do perfil; correção de fecho "
               "inesperado ao remover pessoas alocadas numa tarefa; captura "
               "global de erros com registo em ficheiro de log; separadores "
               "'Perfis' e 'Atividades' renomeados; filtro de estado da "
               "atividade também na vista de Alocação."),
    ("1.2.0", "Filtro de estado multi-seleção e cores por pessoa no calendário; "
               "histórico de custos de perfis com consulta por data; "
               "restauro da base de dados a partir de backup; "
               "numeração de versão visível na aplicação."),
    ("1.1.0", "Base de dados persistente entre instalações; backup; importação "
               "via template Excel; tarefas com datas por defeito do projeto e "
               "alocação em %/horas; calendário em grelha por período; "
               "alocação com filtros de período/cliente/projeto/tarefa."),
    ("1.0.0", "Versão inicial: CRUD de clientes/equipas/perfis/pessoas/projetos/"
               "tarefas, calendário simples, alocação, exportação Excel/PDF, "
               "instalador Windows."),
]

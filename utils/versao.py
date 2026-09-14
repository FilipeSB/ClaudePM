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

VERSAO = "1.2.0"

# Histórico resumido de versões (mais recente primeiro), para referência.
HISTORICO_VERSOES = [
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

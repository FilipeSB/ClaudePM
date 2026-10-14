# Gestão de Pessoas e Projetos

Aplicação desktop (Python + PySide6 + SQLite) para gerir clientes, equipas,
pessoas, perfis de experiência (CC01–CC07), projetos, tarefas e alocações.

## Instalação

1. Ter Python 3.10+ instalado.
2. No diretório do projeto, instalar as dependências:

   ```bash
   pip install -r requirements.txt
   ```

## Executar

```bash
python main.py
```

Na primeira execução é criado automaticamente o ficheiro `dados.db` (SQLite)
na pasta do projeto, já com os 7 perfis (CC01 a CC07) pré-criados com custos
de exemplo — podes editá-los no separador "Perfis".

## Estrutura

```
gestao-projetos/
├── main.py                  # ponto de entrada
├── build_exe.py              # gera o .exe standalone (PyInstaller), sincroniza versão
├── sync_versao.py            # sincroniza utils/versao.py -> version_info.txt / installer.iss
├── version_info.txt          # metadados do .exe (gerado/atualizado por sync_versao.py)
├── installer.iss             # script Inno Setup -> gera o setup.exe
├── assets/
│   └── icon.ico               # ícone da aplicação
├── .github/workflows/
│   └── build.yml              # gera .exe + instalador automaticamente no GitHub
├── database/
│   ├── models.py             # modelos (tabelas) SQLAlchemy, inclui PerfilCustoHistorico
│   └── db.py                 # ligação à BD SQLite + seed inicial + backup/restore
├── utils/
│   ├── versao.py             # número de versão da aplicação (fonte única)
│   ├── calculos.py           # cálculo de custo (com histórico de perfis) + conversão horas/percentagem
│   ├── periodos.py           # navegação por período (semanal/mensal/anual)
│   ├── importacao.py         # geração de template Excel + importação
│   └── exportacao.py         # exportação Excel/PDF
├── ui/
│   ├── base_crud.py          # widget genérico de listagem/formulário
│   ├── filtro_multi_selecao.py  # dropdown com checkboxes (filtro de estado no calendário)
│   ├── janela_principal.py   # janela com separadores + menu Ficheiro (backup/restore/importação)
│   ├── vista_clientes.py
│   ├── vista_equipas.py
│   ├── vista_perfis.py       # inclui histórico de custos por perfil
│   ├── vista_pessoas.py
│   ├── vista_projetos.py     # inclui filtro "custos até uma data"
│   ├── vista_tarefas.py      # datas por defeito do projeto, alocação %/horas
│   ├── vista_calendario.py   # grelha por pessoa, cores próprias, filtro de estado multi-seleção
│   └── vista_alocacao.py     # % de alocação por pessoa, com filtros de período
└── requirements.txt
```

## Funcionalidades incluídas

- CRUD completo de: Clientes, Equipas, Perfis (CC01–CC07), Pessoas, Projetos, Tarefas.
- Perfis com custo/hora e custo/dia associados.
- **Base de dados persistente entre instalações**: fica guardada em
  `%APPDATA%\GestaoProjetos\dados.db` (Windows), fora da pasta de instalação
  do programa — instalar uma versão nova nunca apaga os teus dados. A
  aplicação também migra automaticamente o esquema da BD quando é preciso
  (ex: uma atualização que acrescente colunas novas), sem perder registos.
- **Backup da base de dados**: menu *Ficheiro > Fazer backup da base de
  dados...* — copia o ficheiro `dados.db` atual para onde escolheres.
- **Importação via template Excel**: menu *Ficheiro > Descarregar template
  Excel...* gera um `.xlsx` com uma folha por entidade (Clientes, Equipas,
  Perfis, Pessoas, Projetos, Tarefas, Alocações), já com instruções e um
  exemplo preenchido. Depois de preenchido, *Ficheiro > Importar dados de
  Excel...* cria/atualiza os registos (por nome/código — não duplica se
  já existirem).
- **Tarefas / Atividades**:
  - Ao escolher o projeto, as datas de início/fim ficam por defeito iguais
    às do projeto, mas continuam totalmente editáveis.
  - É possível remover pessoas atribuídas à tarefa diretamente no formulário
    (botão "✕" em cada linha), antes de gravar.
  - A alocação de cada pessoa pode ser em **percentagem** ou em **horas**,
    com uma **categoria** que define o que é "100%": *8 horas / dias úteis*
    (trabalho normal) ou *24 horas / todos os dias* (ex: equipamento ou
    serviço contínuo). Ao introduzir horas, a percentagem é calculada
    automaticamente a partir da categoria escolhida.
- **Calendário** em formato de grelha, com navegação por período **Semanal
  / Mensal / Anual** (anterior/seguinte/hoje). Uma linha por pessoa alocada
  a cada tarefa (colunas: Cliente | Projeto | Atividade | Pessoa | %
  Alocação | Estado da Atividade + colunas de dias/meses), com uma barra
  colorida por dia — **cada pessoa tem uma cor própria e consistente**,
  para se distinguir facilmente quem está alocado a quê. Filtros por
  cliente, projeto e pessoa, e filtro de **estado com seleção múltipla**
  (podes escolher vários estados ao mesmo tempo).
- **Alocação**: percentagem por pessoa, com navegação por período
  (Semanal/Mensal/Anual) e filtros adicionais por Cliente, Projeto e Tarefa
  (em cascata: escolher um cliente filtra os projetos disponíveis, e
  escolher um projeto filtra as tarefas).
- **Histórico de custos dos Perfis**: sempre que alteras o custo/hora ou
  custo/dia de um perfil, a data dessa alteração fica registada (botão
  "Ver histórico de custos" na vista de Perfis). Os custos de projetos são
  calculados usando o custo que estava em vigor na data de início de cada
  tarefa — não o custo atual. Na vista de Projetos podes ainda marcar "Ver
  custos apenas até uma data" para consultar o custo acumulado até esse
  momento (só conta tarefas já iniciadas nessa data).
- **Restauro da base de dados**: menu *Ficheiro > Restaurar base de dados a
  partir de backup...* — substitui os dados atuais pelos de um backup
  escolhido (com confirmação explícita, e guardando automaticamente uma
  cópia de segurança do estado atual antes de o fazer).
- Exportação para Excel e PDF em todas as vistas de listagem, incluindo
  Calendário e Alocação.
- **Número de versão** visível no título da janela (ex: "v1.2.0"), gerido
  centralmente em `utils/versao.py` — ver secção *Versionamento* abaixo.


## Funcionalidades adicionadas (2ª fase)

### 1. Custo automático do projeto
No separador "Projetos" existe agora a coluna **Custo Estimado (€)**, calculada
automaticamente como: `Σ (dias da tarefa × % alocação × custo/dia do perfil da pessoa)`
para todas as tarefas do projeto. Atualiza-se sempre que abres/atualizas a lista.

### 2. Validação de sobre-alocação (>100%)
Ao gravar uma tarefa, a aplicação verifica se alguma pessoa alocada ficaria
com mais de 100% em período sobreposto (considerando todas as outras tarefas
dessa pessoa cujas datas se cruzem). Se detetar isso, mostra um aviso com o
detalhe e pergunta se queres gravar mesmo assim — não bloqueia de forma
irreversível, mas obriga a confirmação consciente.

### 3. Exportação para Excel e PDF
Todos os separadores de listagem (Clientes, Equipas, Perfis, Pessoas,
Projetos, Tarefas, Alocação) têm agora botões **"Exportar Excel"** e
**"Exportar PDF"**, que exportam exatamente os dados visíveis na tabela
(respeitando a ordenação atual).

### 4. Instalador Windows "a sério" (setup.exe com ícone e desinstalador)

A aplicação já vem com um script pronto (`installer.iss`) para a ferramenta
gratuita **Inno Setup**, que gera um `GestaoProjetos-Setup.exe` com:
- Ícone próprio (calendário, em `assets/icon.ico`)
- Atalho no Menu Iniciar e, opcionalmente, no Ambiente de Trabalho
- Entrada em **Definições → Aplicações** (ou Painel de Controlo →
  Programas) para desinstalar como qualquer outro programa
- Não precisa de direitos de administrador (instala na pasta do utilizador)

**Forma mais simples — deixar o GitHub gerar tudo por ti (sem instalar nada):**

1. Cria um repositório novo em https://github.com/new (pode ser privado).
2. Envia esta pasta para esse repositório:
   ```bash
   cd gestao-projetos
   git init
   git add .
   git commit -m "Versão inicial"
   git branch -M main
   git remote add origin https://github.com/<o-teu-utilizador>/<nome-do-repo>.git
   git push -u origin main
   ```
3. No GitHub, abre o separador **Actions** — o workflow corre automaticamente
   (leva ~3-4 minutos: gera o `.exe` e depois o instalador).
4. Quando terminar (✓ verde), abre essa execução, vai a **Artifacts** e
   descarrega **"GestaoProjetos-Setup"** — dentro está o
   `GestaoProjetos-Setup.exe`.
5. Envia esse ficheiro para qualquer PC Windows. Ao correr, abre um
   assistente de instalação normal (idioma português, escolha de pasta,
   opção de ícone no Ambiente de Trabalho). Depois de instalado, aparece
   no Menu Iniciar e pode ser desinstalado a partir de
   **Definições → Aplicações**, como qualquer programa comum.

**Alternativa (gerar localmente, tendo Windows + Python + Inno Setup instalados):**

```bash
pip install -r requirements.txt
python build_exe.py
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

O instalador final fica em `Output/GestaoProjetos-Setup.exe`.

> Nota: se quiseres publicar este instalador para muitas pessoas (fora da
> tua organização), o Windows SmartScreen pode inicialmente assinalar o
> `.exe` como "editor desconhecido" por não estar assinado digitalmente
> (assinatura de código é um serviço pago de terceiros) — isto não impede
> a instalação, apenas mostra um aviso que o utilizador tem de confirmar
> ("Mais informações" → "Executar mesmo assim").

### Reduzir falsos positivos de antivírus / Windows Defender

Foram já aplicadas três medidas gratuitas que reduzem bastante a
probabilidade de o Windows ou um antivírus assinalarem o executável
como suspeito, mesmo sem assinatura digital:

1. **`--onedir` em vez de `--onefile`** — o modo `--onefile` extrai-se
   sozinho para uma pasta temporária sempre que arranca, um padrão de
   comportamento muito associado a malware. Agora gera-se uma pasta normal
   (`GestaoProjetos.exe` + ficheiros de suporte ao lado), sem esse
   comportamento suspeito.
2. **`--noupx`** — desativa a compressão UPX, outro sinal clássico usado
   por heurísticas de antivírus (muito malware também usa UPX para se
   disfarçar).
3. **Metadados de versão** (`version_info.txt`) — o `.exe` passa a ter
   nome de produto, empresa, descrição e versão visíveis nas Propriedades
   do ficheiro no Windows, tornando-o menos "anónimo".

O que **não** está resolvido, por implicar custos:
- **Assinatura digital de código** — é o que faz o Windows mostrar o nome
  do editor em vez de "Editor desconhecido" no SmartScreen, e reduz
  drasticamente os avisos. Certificados pagos custam tipicamente 70-400€/ano.
- **Alternativa gratuita**, já que o teu repositório é público: o
  [SignPath.io](https://signpath.io) oferece assinatura de código gratuita
  para projetos open-source (é usado por projetos como o Git for Windows).
  Requer candidatura e aprovação, mas não tem custo.
- Se o Windows Defender assinalar o ficheiro como vírus (falso positivo),
  podes submetê-lo para análise da Microsoft em
  https://www.microsoft.com/en-us/wdsi/filesubmission — normalmente é
  corrigido em 24-48h e ajuda a "reputação" do ficheiro para todos os
  utilizadores.

## Alterações da v1.6.0

- **Calendário**: corrigido o cinzento que ficava nos cabeçalhos ao mudar de
  período (o Qt reaproveitava os itens do cabeçalho, e a cor de fim de semana
  ficava "colada" à posição da coluna). Agora só os fins de semana ficam a
  cinzento (e os feriados a rosa), em qualquer período.
- **Calendário**: novas colunas **Data de início** e **Data fim** (entre
  Atividade e Pessoa). São ordenáveis e, ao clicar, abre-se um calendário
  para mudar a data (com validação fim ≥ início e aviso de sobre-alocação).
- **Alocação**: a tabela passa a ser só de consulta (o duplo clique já não
  entra em modo de edição).
- **Atividade**: as pessoas alocadas ficam juntas, com o mesmo espaçamento
  dos restantes campos.

## Funcionalidades adicionadas (v1.5.0)

- **Feriados** (*Configurações > Feriados*): lista de feriados que podes
  adicionar/remover à mão ou **importar automaticamente da internet**
  (Portugal, Espanha, Brasil, ...; usa a API pública gratuita
  date.nager.at — requer ligação à internet). Os feriados aparecem a rosa
  no Calendário e não contam como dias de trabalho (nem para a alocação,
  nem para o custo dos projetos).
- **Alocação sempre em dias úteis de 8 horas**: a opção "Categoria" foi
  removida. 8 h = 100%; ao trocar entre percentagem e horas o valor é
  convertido de imediato. Fins de semana e feriados nunca têm alocação.
- **Cor por pessoa** (campo no registo da pessoa): usada nas barras do
  Calendário e da Alocação. As barras da Alocação têm o comprimento
  proporcional à percentagem (acima de 100% ficam cheias, com contorno
  vermelho).
- **Atividades**: ao criar/editar escolhe-se primeiro o Cliente e depois o
  Projeto (só os desse cliente); a listagem tem filtros por Cliente e Projeto.
- **Projetos**: filtro por Cliente.
- **Duplo clique** em qualquer registo (Clientes, Equipas, Perfis, Pessoas,
  Projetos, Atividades) abre a janela de edição.
- **Calendário**: clicar na Pessoa permite trocá-la (lista, como no Estado;
  inclui a opção "Editar a pessoa atual"); clicar na % de Alocação pergunta
  se o valor é em percentagem ou horas (os registos mostram sempre
  percentagem); fins de semana (cinzento) e feriados (rosa) assinalados.
- **Estados**: ao selecionar um estado, o seu nome aparece no campo, pronto
  para editar e renomear.
- O menu **Ajuda** é agora o último (mais à direita).
- A exportação/importação Excel inclui a cor das pessoas; a coluna
  "Categoria" deixou de existir (ficheiros antigos continuam a importar).

## Funcionalidades adicionadas (v1.4.0)

- **Correção de fecho inesperado ao editar Atividades**: a janela de edição
  de uma atividade passou a trabalhar apenas com dados simples (números,
  texto), nunca com objetos ligados a uma sessão da base de dados já
  fechada — essa era a causa mais provável dos fechos inesperados nesta
  operação. Continua também em vigor a rede de segurança geral (qualquer
  erro fica registado em `erros.log`, em vez de fechar a app sem aviso —
  acessível em *Ajuda > Abrir pasta de dados e registo de erros*).
- **Percentagens com 1 casa decimal** em todos os ecrãs (ex: "33.3%").
- **Coluna de ID escondida** em todas as listagens (continua a existir
  internamente, só deixou de ser mostrada).
- **Perfis**: no histórico de custos, é possível eliminar registos
  individuais (botão "Eliminar registo selecionado"), mantendo sempre
  pelo menos um.
- **Projetos**: corrigido o cálculo de custo por data — antes, o custo
  original de cada perfil ficava associado à data de instalação da app,
  o que fazia com que alterações de custo com data de vigência anterior a
  essa fossem ignoradas. Agora o custo original vale "desde sempre", e o
  cálculo percorre corretamente cada período de custo constante do
  histórico. Bases de dados já existentes são corrigidas automaticamente
  ao abrir esta versão (migração de dados, uma única vez).
- **Atividades**: ao escolher o projeto (criar ou editar), mostra-se o
  cliente a que esse projeto pertence; a listagem ganhou uma coluna
  Cliente.
- **Calendário**:
  - Todas as colunas passaram a ser ordenáveis (clicar no cabeçalho).
  - Clicar num Cliente, Projeto, Atividade ou Pessoa abre a respetiva
    janela de edição.
  - Clicar no Estado da Atividade mostra a lista de estados para escolher
    e altera logo esse registo.
  - Clicar na % de Alocação pede um novo valor e grava de imediato
    (com o mesmo aviso de sobre-alocação usado no formulário da atividade).
- **Alocação**: todas as colunas passaram a ser ordenáveis.

## Versionamento

A versão da aplicação segue o esquema semântico `MAJOR.MINOR.PATCH`:
- **MAJOR**: mudanças estruturais grandes (ex: redesenho de uma vista,
  alterações que quebram compatibilidade com instalações antigas).
- **MINOR**: novas funcionalidades.
- **PATCH**: correções e pequenos ajustes, sem funcionalidade nova.

A versão está definida num único sítio: `utils/versao.py` (variável
`VERSAO`), junto com um histórico resumido do que mudou em cada versão.
Isso é a única coisa que precisas de atualizar manualmente a cada ronda
de alterações — tudo o resto sincroniza-se sozinho:

- O **título da janela** mostra sempre a versão atual (ex: "Gestão de
  Pessoas e Projetos — v1.2.0"), lido diretamente de `utils/versao.py`.
- O `build_exe.py` chama `sync_versao.py` automaticamente antes de gerar
  o executável, que atualiza `version_info.txt` (metadados do `.exe`) e
  `installer.iss` (versão do instalador) para o mesmo valor.

Ou seja: quando eu fizer alterações, atualizo a `VERSAO` em
`utils/versao.py` de acordo com o tipo de mudança, e essa versão aparece
automaticamente na aplicação e no instalador gerado — não é preciso editar
mais nenhum ficheiro à mão.

## Próximos passos sugeridos

- Histórico de alterações de estado (auditoria).
- Relatório de custo por cliente/período.
- Multi-utilizador com permissões (atualmente é uma app de utilizador único).

## Nota sobre o Calendário (limitação atual, por transparência)

A grelha do Calendário mostra, por dia (ou mês, na vista Anual), a
**percentagem de alocação** de cada tarefa — calculada a partir da
percentagem definida na tarefa (constante durante toda a sua duração).

O que a grelha **não** faz, ao contrário de folhas de registo de horas
tradicionais: não permite editar um valor de horas célula-a-célula (dia
a dia) diretamente na grelha — isso exigiria alargar o modelo de dados
para guardar valores por dia individual (uma espécie de "timesheet"), o
que é uma funcionalidade maior e distinta da alocação por tarefa que já
existe. Se for isso que precisas (registo de horas reais dia a dia, editável
célula a célula), diz que preparo essa funcionalidade como próximo passo.

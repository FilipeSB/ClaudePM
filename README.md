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
├── build_exe.py              # gera o .exe standalone (PyInstaller)
├── installer.iss             # script Inno Setup -> gera o setup.exe
├── assets/
│   └── icon.ico               # ícone da aplicação
├── .github/workflows/
│   └── build.yml              # gera .exe + instalador automaticamente no GitHub
├── database/
│   ├── models.py             # modelos (tabelas) SQLAlchemy
│   └── db.py                 # ligação à BD SQLite + seed inicial
├── utils/
│   ├── calculos.py           # cálculo de custo de projeto + conversão horas/percentagem
│   ├── periodos.py           # navegação por período (semanal/mensal/anual)
│   ├── importacao.py         # geração de template Excel + importação
│   └── exportacao.py         # exportação Excel/PDF
├── ui/
│   ├── base_crud.py          # widget genérico de listagem/formulário
│   ├── janela_principal.py   # janela com separadores + menu Ficheiro
│   ├── vista_clientes.py
│   ├── vista_equipas.py
│   ├── vista_perfis.py
│   ├── vista_pessoas.py
│   ├── vista_projetos.py
│   ├── vista_tarefas.py      # datas por defeito do projeto, alocação %/horas
│   ├── vista_calendario.py   # grelha Cliente/Projeto/Tarefa/Deadline + dias
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
- **Calendário** em formato de grelha (Cliente | Projeto | Tarefa | Deadline
  + colunas de dias/meses), com navegação por período **Semanal / Mensal /
  Anual** (anterior/seguinte/hoje) e filtros por cliente, projeto, pessoa e
  estado. Cada célula mostra uma barra colorida com a percentagem de
  alocação da tarefa nesse dia (ou mês, na vista anual):
  - cinzento = sem alocação nesse período
  - amarelo = alocação parcial (<100%)
  - verde = 100%
  - vermelho = sobre-alocado (>100%)
- **Alocação**: a mesma lógica de percentagem por pessoa, agora com
  navegação por período (Semanal/Mensal/Anual) e filtros adicionais por
  Cliente, Projeto e Tarefa (em cascata: escolher um cliente filtra os
  projetos disponíveis, e escolher um projeto filtra as tarefas).
- Exportação para Excel e PDF em todas as vistas de listagem, incluindo
  Calendário e Alocação.


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

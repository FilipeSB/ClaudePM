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
│   ├── calculos.py           # cálculo de custo de projeto
│   └── exportacao.py         # exportação Excel/PDF
├── ui/
│   ├── base_crud.py          # widget genérico de listagem/formulário
│   ├── janela_principal.py   # janela com separadores
│   ├── vista_clientes.py
│   ├── vista_equipas.py
│   ├── vista_perfis.py
│   ├── vista_pessoas.py
│   ├── vista_projetos.py
│   ├── vista_tarefas.py      # inclui gestão de alocações (pessoas + %)
│   ├── vista_calendario.py   # calendário com filtros
│   └── vista_alocacao.py     # % de alocação por pessoa, com alertas
└── requirements.txt
```

## Funcionalidades incluídas

- CRUD completo de: Clientes, Equipas, Perfis (CC01–CC07), Pessoas, Projetos, Tarefas.
- Perfis com custo/hora e custo/dia associados.
- Tarefas com data início/fim, estado, e alocação de pessoas com percentagem
  (editável diretamente no formulário da tarefa).
- Calendário com filtros por cliente, projeto, equipa, pessoa e estado —
  ao clicar num dia, mostra as tarefas ativas nesse dia.
- Vista de Alocação: percentagem total de cada pessoa nas tarefas em curso
  hoje, com destaque de cor:
  - cinzento = sem alocação
  - amarelo = alocação parcial (<100%)
  - verde = 100% alocado
  - vermelho = sobre-alocado (>100%)

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

## Próximos passos sugeridos

- Histórico de alterações de estado (auditoria).
- Relatório de custo por cliente/período.
- Multi-utilizador com permissões (atualmente é uma app de utilizador único).

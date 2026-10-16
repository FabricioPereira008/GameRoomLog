# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [0.3.1] - 2026-10-16
### Corrigido
- AppImage agora abre em distribuições sem libfuse.so.2 (ex.: Arch/CachyOS com apenas FUSE 3): o build passou a usar o appimagetool atual, com runtime estático.
- O workflow de release verifica o runtime do AppImage e faz um smoke test do app extraído antes de publicar.

## [0.3.0] - 2026-10-16
### Adicionado
- Nova interface: design system com tokens (cores, raios, tipografia), fonte Inter embutida e ícones SVG no lugar dos emojis; sidebar com seções e itens ativos destacados.
- Grades de jogos virtualizadas (model/view com delegate): carregar e filtrar 600 jogos leva poucos milissegundos; capas carregadas em segundo plano com cache limitado.
- Biblioteca em tabela ordenável por coluna (ordenação numérica) e status coloridos.
- Migrações de banco com Alembic (bancos existentes são adotados sem perda de dados).
- Salvar, excluir e carregar listas/capas sem travar a interface; logs em arquivo rotativo.
- CI em push/PR com cobertura mínima de 70%, hook de pré-commit versionado e dependências de build travadas (constraints-build.txt).

### Segurança
- CORS restrito a origens locais; proteção contra SSRF e limite de tamanho nos downloads de capa; validação de imagens enviadas; chave da SteamGridDB no corpo da requisição.

### Modificado
- Camada de serviços para gêneros, plataformas, franquias e desenvolvedoras; contagens em consulta única; chaves estrangeiras habilitadas no SQLite; validação de campos (título, notas 0-10, horas).
- Versão do app centralizada em app_version.py.

### Corrigido
- Exclusão de jogo agora respeita a resposta do servidor; fallback de data da platina; configurações rolável em janelas baixas; recorte de capa não grava mais no armazenamento do backend.

## [0.2.4] - 2026-08-24
### Adicionado
- Pipeline de CI/CD automatizado no GitHub Actions para geração de AppImage (Linux) e executáveis .EXE (Windows).
- Launcher unificado `desktop_launcher.py` para execução standalone de 1 clique.
- Suporte a persistência de banco de dados e capas nos diretórios padrão do usuário (XDG no Linux e AppData no Windows).
- Ícone oficial do aplicativo empacotado nos binários.

### Corrigido
- Renderização do tema escuro no Windows em modais (`GameDialog`), cabeçalhos de tabela e contêineres de rolagem.
- Rótulo dinâmico de identificação do sistema operacional na barra lateral.

## [0.2.3] - 2026-08-22
### Adicionado
- Campo de busca instantânea por título nas páginas Game Room, Fila, Disponíveis, Zerados e Platinados.
- Painel de filtros avançados retrátil (Gênero, Desenvolvedora, Plataforma, Franquia e Tempo HLTB).
- Badge de contagem e destaque visual para filtros ativos no botão de alternância.
- Campos Franquia/Série e Gênero editáveis com autocompletar e auto-criação no GameDialog.
- Suíte de testes unitários para o sistema de busca e painel de filtros.

### Modificado
- Limpeza automática de busca e filtros ao navegar pela Sidebar.
- Estilização do Dark Theme para suporte a formulários de busca e filtros.

## [0.2.2] - 2026-08-22
### Adicionado
- Suíte completa de 31 testes automatizados (Backend, Frontend isolado e Testes de Performance).
- Pré-commit hook para validação obrigatória dos testes antes de commits.
- Otimização de renderização dinâmica em lotes para monitores widescreen.

### Corrigido
- Ajuste de visibilidade condicional na janela de edição de jogos (`GameDialog`) ocultando campos irrelevantes.

## [0.2.1] - 2026-08-22
### Otimizado
- Cache em memória de capas (`_COVER_PIXMAP_CACHE`) reduzindo engasgos no scroll para 0.0001ms.
- Reposicionamento instantâneo de grade ao deletar itens (`relayout_cards(force=True)`).

## [0.2.0] - 2026-08-22
### Adicionado
- Formulários condicionais para status Zerado e Platinado (Horas, Nota, Dificuldade, Datas).
- Botão "Carregar Mais" (`LoadMoreCard`) para paginação sob demanda no Game Room.
- Mutações in-place na UI evitando recarregamento total da janela principal.

## [0.1.3] - 2026-08-21
### Otimizado
- Layout adaptativo ocupando toda a largura da tela.
- Carregamento assíncrono antecipado nas páginas de categorias.

# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.2.0] - 2026-10-17
### Adicionado
- Jogos podem ter **dois gêneros**: principal e secundário (opcional), com um novo campo "Gênero secundário" na janela de jogo.
- Os cards mostram os dois gêneros: o principal em destaque e o secundário com contorno na cor do gênero; o tooltip do card lista os dois nomes completos.
- O filtro por gênero também encontra jogos pelo gênero secundário.

### Modificado
- A plataforma passou para a linha de horas e nota do card, mantendo a mesma altura.
- Migração `0004_genre_position`: a ordem dos gêneros (principal/secundário) é guardada no banco; a API aceita no máximo dois gêneros por jogo e devolve o principal primeiro.

## [1.1.0] - 2026-10-17
### Adicionado
- Importar pela **Sincronização de lojas** agora abre a tela de informações de cada jogo selecionado, já preenchida (título, horas jogadas, PC, Digital, Disponível), para completar os dados antes de salvar. O jogo só é criado ao salvar; cancelar mantém o item na lista e pergunta se deseja continuar com os próximos.
- Endpoint `POST /api/v1/library/link` para vincular um jogo já cadastrado a um item da loja.

### Modificado
- Após salvar, o jogo é vinculado à loja e ganha capa automática se nenhuma foi escolhida.
- A janela de jogo aceita a plataforma pré-preenchida pelo nome.

## [1.0.0] - 2026-10-17
### Adicionado
- Integração com o app Android **GameRoom Portátil** ([GameRoomApp](https://github.com/FabricioPereira008/GameRoomApp)): registre no portátil o que está jogando, zerou ou platinou e importe no PC.
- Caixa de entrada em **Configurações → App do Portátil**: importar o arquivo do app, revisar os pendentes e exportar o catálogo para o app sugerir títulos e plataformas.
- Revisão por jogo, com correspondência por semelhança (limite configurável), confirmação de jogos parecidos, aviso de plataforma diferente e tabela atual → proposto. Também é possível vincular a outro jogo ou criar um jogo novo já preenchido.
- Regras automáticas: rejogada sugerida quando o jogo já está zerado, platina sem data de zeramento propõe a mesma data, horas/nota/dificuldade usam o último valor e observações são acrescentadas.
- Contratos JSON versionados em `docs/contracts/` (`gameroom-inbox` v1 e `gameroom-catalog` v1) e API `/api/v1/inbox` (import, pending, proposal, resolve, catalog).

### Modificado
- Reimportar o mesmo arquivo não duplica nada (UUID por evento, nova tabela `inbox_events`).
- A janela de jogo aceita dados pré-preenchidos também para jogos novos.

## [0.4.2] - 2026-10-16
### Modificado
- Páginas de Gêneros, Plataformas e Séries / Franquias redesenhadas: cards estilo pôster com mosaico das capas dos jogos (inteiras, sem corte), faixa com a cor do gênero, selo de plataforma, total de horas e menu ⋯ (Editar/Excluir) ao passar o mouse.
- A API de categorias passa a devolver `cover_samples` e `total_hours`.
- Páginas de detalhe ganharam ordenação por nome, nota ou horas; o filtro da própria categoria fica visível, mas bloqueado.

### Corrigido
- Filtros por gênero, desenvolvedora, plataforma e franquia agora filtram enquanto você digita (por trecho do nome) e o campo de seleção abre a lista de sugestões.

## [0.4.1] - 2026-10-16
### Modificado
- Janela de adicionar/editar jogo redesenhada: campos organizados em cartões (Identificação, Progresso, Jogada, Anotações), rótulos acima dos campos, coluna própria para a capa com preview maior e botão Enter para salvar.
- Ao criar um jogo, todos os campos começam em branco ou com texto neutro (status, plataforma e formato com “Selecione…”, datas vazias, horas e notas sem valor); título e status são obrigatórios.
- Tipo de jogada virou o checkbox “Esta é uma rejogada”; as datas de conclusão começam vazias e abrem o calendário no mês atual.

### Corrigido
- Desenvolvedora, franquia e gênero vinham preenchidos com o primeiro item da lista em jogos novos.
- Ajustar recorte da capa falhava ao limpar o arquivo temporário (faltava importar os).
- Jogos da Steam com apóstrofo no título (ex.: Dragon's Dogma 2) agora são reconhecidos como já cadastrados.

## [0.4.0] - 2026-10-16
### Adicionado
- Sincronização de bibliotecas de lojas: nova tela “Sincronizar lojas” lista os jogos da Steam, Epic, GOG e Amazon que ainda não estão no GameRoom e importa os escolhidos (tudo vem desmarcado, com busca, filtro por loja e “só jogados”).
- Steam via API oficial (API key e SteamID64 salvos apenas no computador); Epic, GOG e Amazon lidos do Heroic Games Launcher, em modo somente leitura.
- Jogos já cadastrados à mão são vinculados automaticamente à loja pelo título; jogos ignorados não reaparecem e podem ser restaurados.
- Capas dos jogos importados são buscadas em segundo plano.

### Modificado
- Nova migração de banco (vínculos de loja e lista de ignorados); bancos existentes são atualizados sem perda de dados.

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

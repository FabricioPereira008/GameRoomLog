# Changelog

Todas as alterações notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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

# GameRoomLog — Regras e Diretrizes do Projeto

Este arquivo define as convenções e padrões arquiteturais a serem seguidos pelo Antigravity neste repositório.

## 1. Padrões de Código e Arquitetura
- **Backend (FastAPI):** Mantenha a separação em camadas: rotas em `backend/app/api/v1/endpoints/`, regras de negócio em `backend/app/services/` e schemas em `backend/app/schemas/`. Nunca faça queries SQL diretamente dentro dos endpoints da API.
- **Frontend (PySide6):** O frontend não acessa o banco de dados diretamente; todas as operações devem passar exclusivamente pelo `ApiClient` (`frontend_desktop/api_client/client.py`).
- **UI Performance:** Mantenha as mutações de interface in-place (usando `insert_game`, `update_game`, `remove_game`) evitando recarregamentos totais da tela (`refresh_all_data`) desnecessários.
- **Visibilidade de Campos:** Na criação e edição de jogos (`GameDialog`), use `setVisible(False)` para campos condicionais irrelevantes ao status selecionado.

## 2. Testes e Cobertura Obrigatória (Workflow de Funcionalidades)
- Qualquer nova funcionalidade ou refatoração no backend ou frontend **DEVE** ter cobertura de testes automatizados criada antes de ser finalizada, seguindo a skill `.agents/skills/ensure-test-coverage/SKILL.md`.
- Teste sempre caminhos felizes e casos de erro (404/422/campos vazios).
- O pré-commit hook do Git está ativo e bloqueará commits se os testes falharem.

## 3. Lançamento de Novas Versões
- Ao lançar uma nova versão, utilize o workflow definido na skill `.agents/skills/release-version/SKILL.md` ou execute o helper `.agents/skills/release-version/scripts/release.py <VERSAO>`.

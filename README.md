# 🕹️ GameRoomLog

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PySide6](https://img.shields.io/badge/PySide6-Qt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Pytest](https://img.shields.io/badge/Tests-36%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

**Seu gerenciador pessoal de backlog de jogos, histórico de gameplay e anuário gamer definitivo.**

</div>

---

## 📖 Sobre o Projeto

O **GameRoomLog** é um aplicativo desktop nativo e moderno desenvolvido para gerenciar, catalogar e visualizar o seu histórico completo de jogos. Ele combina uma interface gráfica moderna e fluida construída em **PySide6 (Qt)** com a robustez e desacoplamento de uma **API REST em FastAPI**, tudo rodando localmente com altíssima performance.

---

## ✨ Funcionalidades Principais

- 🎮 **Game Room Visual:** Visão geral dos jogos que você está jogando agora, próximos na lista, fila de espera, zerados e platinados.
- 🔍 **Busca & Filtros Avançados:** Busca instantânea por título e painel retrátil de filtros em tempo real (Gênero, Desenvolvedora, Plataforma, Franquia e Tempo HLTB).
- 📅 **Anuário Gamer (Yearbook):** Estatísticas detalhadas por ano (horas jogadas, jogos finalizados, platinas conquistadas e médias de avaliação).
- ⚡ **Performance Zero-Stutter:** Cache inteligente em memória para capas (`QPixmap`), rolagem antecipada suave e carregamento sob demanda em lotes dinâmicos.
- 🏷️ **Gestão Completa de Categorias:** Organização por Plataformas, Gêneros, Desenvolvedoras e Franquias com autocompletar inteligente e auto-criação.
- 📦 **Importador do Notion:** Migre facilmente seu banco de dados anterior do Notion (CSV/Markdown) com detecção automática de capas e metadados.
- 🧪 **100% Testado:** Suíte com 36 testes automatizados (Backend, Mock de Frontend e Testes de Performance em milissegundos).


---

## 🏛️ Arquitetura do Software

O GameRoomLog utiliza uma **Arquitetura Client-Server Desacoplada**:

```mermaid
graph TD
    UI[Frontend Desktop - PySide6] -->|HTTP / JSON Requests| API[Backend REST API - FastAPI]
    API -->|Validação & Schemas| Pydantic[Pydantic DTOs]
    API -->|Regras de Negócio| Services[Service Layer]
    Services -->|ORM Mapping| SQLAlchemy[SQLAlchemy ORM]
    SQLAlchemy -->|Persistência Local| DB[(SQLite Database)]
```

> **Pronto para Expansão:** Como o Frontend consome o Backend estritamente via API REST HTTP (`ApiClient`), o ecossistema está preparado para receber futuros clientes **Web (React/Vue)** ou **Mobile (Flutter/React Native)** sem necessidade de alterações no servidor.

---

## 🚀 Como Executar o Projeto

### Pré-requisitos
- **Python 3.11+**
- Ambiente Linux (otimizado para Wayland/X11 no CachyOS / Arch / Ubuntu) ou Windows/macOS.

### 1. Clonar o Repositório
```bash
git clone https://github.com/SEU_USUARIO/GameRoomLog.git
cd GameRoomLog
```

### 2. Criar e Ativar o Ambiente Virtual
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar as Dependências
```bash
pip install -r backend/requirements.txt
pip install -r frontend_desktop/requirements.txt
```

### 4. Iniciar a Aplicação (Backend + Frontend)
Execute o script agregador:
```bash
python run_all.py
```
*Ou, se preferir rodar em terminais separados:*
```bash
# Terminal 1: Backend
python run_dev.py

# Terminal 2: Frontend Desktop
python frontend_desktop/main_app.py
```

---

## 🧪 Testes Automatizados e Qualidade

O projeto possui cobertura completa com `pytest` e testes de performance:

```bash
# Executar todos os testes
pytest -v

# Executar com relatório de cobertura de código
pytest --cov=backend/app --cov=frontend_desktop/api_client --cov-report=term-missing
```

### Hook de Pré-Commit
O repositório já inclui validação automática pré-commit (`.git/hooks/pre-commit`). Commits serão bloqueados caso algum teste automatizado falhe.

---

## 📂 Estrutura de Diretórios

```text
GameRoomLog/
├── backend/                  # Servidor FastAPI
│   ├── app/
│   │   ├── api/v1/          # Rotas e Endpoints HTTP
│   │   ├── core/            # Configurações e Banco de Dados
│   │   ├── models/          # Entidades SQLAlchemy
│   │   ├── schemas/         # Modelos Pydantic (Validação)
│   │   └── services/        # Regras de Negócio e Serviços
│   ├── storage/covers/      # Armazenamento local de capas
│   └── tests/               # Testes de integração e unitários do Backend
├── frontend_desktop/         # Interface Desktop PySide6
│   ├── api_client/          # Cliente HTTP desacoplado
│   ├── styles/              # Folhas de estilo QSS (Dark Theme)
│   ├── views/               # Janelas, Componentes e Diálogos
│   └── tests/               # Testes de mutação de estado e performance da UI
├── .agents/                  # Skills e Workflows do Antigravity
├── AGENTS.md                 # Diretrizes e regras arquiteturais do projeto
├── CHANGELOG.md              # Histórico de versões (Keep a Changelog)
├── pytest.ini                # Configuração global de testes
└── run_all.py                # Inicializador conjunto da aplicação
```

---

## 📄 Licença

Este projeto está sob a licença [MIT](LICENSE).

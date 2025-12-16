# PyStock Manager 📦

![Badge em Desenvolvimento](http://img.shields.io/static/v1?label=STATUS&message=EM%20DESENVOLVIMENTO&color=GREEN&style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Backend-Flask-lightgrey?style=for-the-badge&logo=flask)
![PySide6](https://img.shields.io/badge/Frontend-PySide6-green?style=for-the-badge&logo=qt)

> Sistema de Gestão de Estoque Full-Stack (Desktop Client + API Server) desenvolvido em Python.

## 💻 Sobre o Projeto

O **PyStock Manager** é uma solução robusta para controlo de inventário, desenhada com arquitetura Cliente-Servidor. O objetivo é fornecer uma ferramenta ágil para pequenas empresas gerirem produtos, fornecedores e movimentações de estoque em rede local.

**Destaques:**
* 📡 **Arquitetura Desacoplada:** Backend (API REST) separado do Frontend (Desktop).
* 🔒 **Segurança:** Autenticação via JWT e senhas com hash (Scrypt).
* 📊 **Relatórios:** Geração automática de PDFs para inventário e etiquetas de código de barras.
* 🖥️ **Interface Moderna:** UI responsiva construída com PySide6 (Qt) e temas Dark/Light.

---

## ⚙️ Arquitetura

O projeto está dividido em dois módulos principais:

| Módulo | Tecnologia | Descrição |
|---|---|---|
| **Backend** | Python / Flask / SQLAlchemy | API RESTful que gerencia regras de negócio e acesso ao Banco MySQL. |
| **Frontend** | Python / PySide6 | Aplicação Desktop que consome a API e fornece a interface ao utilizador. |

---

## 🚀 Como Rodar Localmente

### Pré-requisitos
* Python 3.10+
* MySQL Server
* Git

### 1. Clonar e Configurar
```bash
git clone [https://github.com/SEU_USUARIO/pystock-manager.git](https://github.com/SEU_USUARIO/pystock-manager.git)
cd pystock-manager
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar Banco de Dados

Crie um banco de dados MySQL chamado estoque_db. Configure as credenciais no arquivo .env ou nas variáveis de ambiente do sistema (ver backend/app.py).

### 3. Executar o Backend (Servidor)
```bash
cd backend
python run_server.py
# O servidor iniciará em http://localhost:5000
```

### 4. Executar o Frontend (Cliente)

Abra um novo terminal:

```bash
cd frontend_desktop
python run.py
```

### 🛠️ Funcionalidades

    [x] Cadastro de Produtos com Foto e Código de Barras

    [x] Entrada e Saída de Estoque (com validação de saldo)

    [x] Gestão de Fornecedores e Categorias (Naturezas)

    [x] Geração de Etiquetas (PDF)

    [x] Dashboard com KPIs Financeiros

    [x] Modo "Terminal" para leitura rápida de códigos de barras

    [x] Controle de Acesso (Admin/Usuário)


### 🤝 Como Contribuir

    Faça um Fork do projeto.

    Crie uma Branch para sua feature (git checkout -b feature/MinhaFeature).

    Faça o Commit (git commit -m 'Adicionando MinhaFeature').

    Faça o Push (git push origin feature/MinhaFeature).

    Abra um Pull Request.


### 📝 Licença

Este projeto está sob a licença MIT - veja o arquivo LICENSE para detalhes.

Desenvolvido por Matheus Lopes 
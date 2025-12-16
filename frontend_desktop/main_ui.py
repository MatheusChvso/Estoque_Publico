# ==============================================================================
# 1. IMPORTS
# ==============================================================================
import sys
import os
import requests
import traceback
import json
import random
import webbrowser
import winsound
import threading

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QMessageBox, QMainWindow, QHBoxLayout, QStackedWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QDialog, QFormLayout,
    QDialogButtonBox, QListWidget, QListWidgetItem, QAbstractItemView,
    QComboBox, QFileDialog, QFrame, QDateEdit, QCalendarWidget, QMenu,
    QTextEdit, QTabWidget, QProgressBar, QSpinBox, QCheckBox, QGroupBox,
    QGridLayout, QScrollArea, QInputDialog, QRadioButton, QButtonGroup
)
from PySide6.QtGui import (
    QPixmap, QAction, QDoubleValidator, QKeySequence, QIcon
)
from PySide6.QtCore import (
    Qt, QTimer, Signal, QDate, QEvent, QObject, QThread, QUrl, QSettings
)
from PySide6.QtMultimedia import QSoundEffect
from packaging.version import parse as parse_version

from config import SERVER_IP

# ==============================================================================
# 2. FUNÇÕES AUXILIARES E VARIÁVEIS GLOBAIS
# ==============================================================================
access_token = None
API_BASE_URL = f"http://{SERVER_IP}:5000"
APP_VERSION = "2.5"
CURRENT_THEME = 'light'

print("--- INICIANDO APLICAÇÃO ---")
print(f"--- IP DO SERVIDOR: '{SERVER_IP}' ---")

class SignalHandler(QObject):
    fornecedores_atualizados = Signal()
    naturezas_atualizadas = Signal()

signal_handler = SignalHandler()

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def show_connection_error_message(parent):
    QMessageBox.critical(parent,
        "Erro de Conexão",
        "Impossível conectar ao servidor.\n\n"
        "Verifique:\n"
        "1. Se o servidor está ligado.\n"
        "2. Se há conexão com a rede.\n"
        "3. Se o IP no 'config.py' está correto."
    )

def load_stylesheet(theme_name):
    global CURRENT_THEME
    filename = "style.qss" if theme_name == "light" else "style_dark.qss"
    try:
        with open(resource_path(filename), "r", encoding="utf-8") as f:
            CURRENT_THEME = theme_name
            return f.read()
    except FileNotFoundError:
        print(f"AVISO: Arquivo de estilo ({filename}) não encontrado.")
        return ""

def check_for_updates():
    print("A verificar atualizações...")
    try:
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(f"{API_BASE_URL}/api/versao", headers=headers, timeout=5)

        if response.status_code == 200:
            dados_versao = response.json()
            versao_servidor = dados_versao.get("versao")
            url_download = dados_versao.get("url_download")

            if versao_servidor and parse_version(versao_servidor) > parse_version(APP_VERSION):
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setWindowTitle("Nova Versão Disponível!")
                msg_box.setText(f"Versão {versao_servidor} disponível.")
                msg_box.setInformativeText("Deseja ir para a página de download?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
                
                if msg_box.exec() == QMessageBox.StandardButton.Yes:
                    webbrowser.open(url_download)
            else:
                print("Aplicação atualizada.")
    except Exception as e:
        print(f"Erro ao verificar atualizações: {e}")

# ==============================================================================
# 3. JANELAS DE DIÁLOGO E WORKERS
# ==============================================================================

class ApiWorker(QObject):
    finished = Signal(int, object)

    def __init__(self, method, endpoint, params=None, json_data=None, files=None, form_data=None):
        super().__init__()
        self.method = method
        self.endpoint = endpoint
        self.params = params
        self.json_data = json_data
        self.files = files
        self.form_data = form_data

    def run(self):
        global access_token, API_BASE_URL
        headers = {'Authorization': f'Bearer {access_token}'}
        url = f"{API_BASE_URL}{self.endpoint}"

        try:
            response = requests.request(
                self.method, url, headers=headers, params=self.params, 
                files=self.files, data=self.form_data, timeout=15
            )
            data = response.json() if response.content else {}
            self.finished.emit(response.status_code, data)
        except requests.exceptions.RequestException as e:
            self.finished.emit(-1, {"erro": f"Erro de conexão: {e}"})
        except Exception as e:
            self.finished.emit(-2, {"erro": f"Erro inesperado: {e}"})

class FormDataLoader(QObject):
    finished = Signal(dict)

    def __init__(self, produto_id):
        super().__init__()
        self.produto_id = produto_id

    def run(self):
        results = {'status': 'success'}
        try:
            global access_token
            headers = {'Authorization': f'Bearer {access_token}'}
            params = {}
            if self.produto_id:
                params['produto_id'] = self.produto_id
            
            response = requests.get(f"{API_BASE_URL}/api/formularios/produto_data", headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results['fornecedores'] = data.get('fornecedores', [])
            results['naturezas'] = data.get('naturezas', [])
            if data.get('produto'):
                results['produto'] = data['produto']
        except requests.exceptions.RequestException:
            results['status'] = 'error'
            results['message'] = "connection_error"
        except Exception as e:
            results['status'] = 'error'
            results['message'] = f"Erro inesperado: {e}"
        
        self.finished.emit(results)

class FormularioProdutoDialog(QDialog):
    produto_atualizado = Signal(int, dict)

    def __init__(self, parent=None, produto_id=None, row=None):
        super().__init__(parent)
        self.produto_id = produto_id
        self.row = row
        self.setWindowTitle("Adicionar Novo Produto" if self.produto_id is None else "Editar Produto")
        self.setMinimumSize(450, 600)
        
        self.layout = QFormLayout(self)
        self.dados_produto_carregados = None
        
        self.input_codigo = QLineEdit()
        self.input_nome = QLineEdit()
        self.input_descricao = QLineEdit()
        self.input_preco = QLineEdit()
        self.input_preco.setValidator(QDoubleValidator(0.00, 999999.99, 2))
        self.input_codigoB = QLineEdit()
        self.input_codigoC = QLineEdit()
        
        self.lista_fornecedores = QListWidget()
        self.lista_fornecedores.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.lista_fornecedores.setMaximumHeight(100)
        
        self.lista_naturezas = QListWidget()
        self.lista_naturezas.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.lista_naturezas.setMaximumHeight(100)
        
        self.label_status_codigo = QLabel("")
        self.label_status_codigo.setFixedWidth(100)
        
        self.btn_add_fornecedor = QPushButton("+")
        self.btn_add_fornecedor.setFixedSize(25, 25)
        self.btn_add_fornecedor.setObjectName("btnQuickAdd")
        
        self.btn_add_natureza = QPushButton("+")
        self.btn_add_natureza.setFixedSize(25, 25)
        self.btn_add_natureza.setObjectName("btnQuickAdd")
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        
        self.verificacao_timer = QTimer(self)
        self.verificacao_timer.setSingleShot(True)
        self.verificacao_timer.timeout.connect(self.verificar_codigo_produto)
        
        layout_codigo = QHBoxLayout()
        layout_codigo.addWidget(self.input_codigo)
        layout_codigo.addWidget(self.label_status_codigo)
        
        self.layout.addRow("Código:", layout_codigo) 
        self.layout.addRow("Nome:", self.input_nome)
        self.layout.addRow("Descrição:", self.input_descricao)
        self.layout.addRow("Preço:", self.input_preco)
        self.layout.addRow("Código B:", self.input_codigoB)
        self.layout.addRow("Código C:", self.input_codigoC)
        
        layout_forn = QHBoxLayout()
        layout_forn.addWidget(QLabel("Fornecedores:"))
        layout_forn.addWidget(self.btn_add_fornecedor)
        layout_forn.addStretch(1)
        
        layout_nat = QHBoxLayout()
        layout_nat.addWidget(QLabel("Naturezas:"))
        layout_nat.addWidget(self.btn_add_natureza)
        layout_nat.addStretch(1)
        
        self.layout.addRow(layout_forn)
        self.layout.addRow(self.lista_fornecedores)
        self.layout.addRow(layout_nat)
        self.layout.addRow(self.lista_naturezas)
        self.layout.addWidget(self.botoes)
        
        self.input_codigo.installEventFilter(self)
        self.input_codigo.textChanged.connect(self.iniciar_verificacao_timer)
        self.input_codigoC.returnPressed.connect(self.botoes.button(QDialogButtonBox.StandardButton.Save).click)
        self.btn_add_fornecedor.clicked.connect(self.adicionar_rapido_fornecedor)
        self.btn_add_natureza.clicked.connect(self.adicionar_rapido_natureza)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        
        self.iniciar_carregamento_assincrono()

    def iniciar_carregamento_assincrono(self):
        self.definir_estado_carregamento(True)
        self.thread = QThread()
        self.worker = FormDataLoader(self.produto_id)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.preencher_dados_formulario)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def definir_estado_carregamento(self, a_carregar):
        for widget in self.findChildren(QWidget):
            if isinstance(widget, (QLineEdit, QListWidget, QPushButton)):
                widget.setEnabled(not a_carregar)
        if a_carregar:
            self.loading_label = QLabel("A carregar dados do servidor...")
            self.layout.addRow(self.loading_label)
        else:
            if hasattr(self, 'loading_label'):
                self.loading_label.hide()
                self.loading_label.deleteLater()

    def preencher_dados_formulario(self, resultados):
        self.definir_estado_carregamento(False)
        if resultados['status'] == 'error':
            if resultados['message'] == 'connection_error':
                show_connection_error_message(self)
            else:
                QMessageBox.critical(self, "Erro de Carregamento", resultados['message'])
            self.reject()
            return

        for forn in resultados.get('fornecedores', []):
            item = QListWidgetItem(forn['nome'])
            item.setData(Qt.UserRole, forn['id'])
            self.lista_fornecedores.addItem(item)

        for nat in resultados.get('naturezas', []):
            item = QListWidgetItem(nat['nome'])
            item.setData(Qt.UserRole, nat['id'])
            self.lista_naturezas.addItem(item)

        if 'produto' in resultados:
            self.dados_produto_carregados = resultados['produto']
            dados = self.dados_produto_carregados
            self.input_codigo.setText(dados.get('codigo', ''))
            self.input_nome.setText(dados.get('nome', ''))
            self.input_descricao.setText(dados.get('descricao', ''))
            self.input_preco.setText(str(dados.get('preco', '0.00')))
            self.input_codigoB.setText(dados.get('codigoB', ''))
            self.input_codigoC.setText(dados.get('codigoC', ''))
            self.selecionar_itens_nas_listas(dados)

    def eventFilter(self, source, event):
        if source is self.input_codigo and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.input_nome.setFocus()
                return True
        return super().eventFilter(source, event)

    def iniciar_verificacao_timer(self):
        if self.produto_id is None:
            self.label_status_codigo.setText("Verificando...")
            self.verificacao_timer.stop()
            self.verificacao_timer.start(500)

    def verificar_codigo_produto(self):
        codigo = self.input_codigo.text().strip()
        if not codigo:
            self.label_status_codigo.setText("")
            return
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f"{API_BASE_URL}/api/produtos/codigo/{codigo}", headers=headers)
            if response and response.status_code == 404:
                self.label_status_codigo.setText("✅ Disponível")
                self.label_status_codigo.setStyleSheet("color: #28a745;")
            elif response and response.status_code == 200:
                self.label_status_codigo.setText("❌ Já existe!")
                self.label_status_codigo.setStyleSheet("color: #dc3545;")
            else:
                self.label_status_codigo.setText("")
        except requests.exceptions.RequestException:
            self.label_status_codigo.setText("⚠️ Erro")
            self.label_status_codigo.setStyleSheet("color: #ffc107;")

    def adicionar_rapido_fornecedor(self):
        dialog = QuickAddDialog(self, "Adicionar Novo Fornecedor", "/api/fornecedores")
        dialog.item_adicionado.connect(self.carregar_listas_de_apoio_refreshed)
        dialog.exec()

    def adicionar_rapido_natureza(self):
        dialog = QuickAddDialog(self, "Adicionar Nova Natureza", "/api/naturezas")
        dialog.item_adicionado.connect(self.carregar_listas_de_apoio_refreshed)
        dialog.exec()

    def carregar_listas_de_apoio_refreshed(self):
        self.carregar_listas_de_apoio()
        if self.dados_produto_carregados:
            self.selecionar_itens_nas_listas(self.dados_produto_carregados)

    def carregar_listas_de_apoio(self):
        self.lista_fornecedores.clear()
        self.lista_naturezas.clear()
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response_forn = requests.get(f"{API_BASE_URL}/api/fornecedores", headers=headers)
            if response_forn and response_forn.status_code == 200:
                for forn in response_forn.json():
                    item = QListWidgetItem(forn['nome'])
                    item.setData(Qt.UserRole, forn['id'])
                    self.lista_fornecedores.addItem(item)
            
            response_nat = requests.get(f"{API_BASE_URL}/api/naturezas", headers=headers)
            if response_nat and response_nat.status_code == 200:
                for nat in response_nat.json():
                    item = QListWidgetItem(nat['nome'])
                    item.setData(Qt.UserRole, nat['id'])
                    self.lista_naturezas.addItem(item)
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def selecionar_itens_nas_listas(self, dados_produto):
        ids_fornecedores = {f['id'] for f in dados_produto.get('fornecedores', [])}
        for i in range(self.lista_fornecedores.count()):
            item = self.lista_fornecedores.item(i)
            if item.data(Qt.UserRole) in ids_fornecedores:
                item.setSelected(True)
        
        ids_naturezas = {n['id'] for n in dados_produto.get('naturezas', [])}
        for i in range(self.lista_naturezas.count()):
            item = self.lista_naturezas.item(i)
            if item.data(Qt.UserRole) in ids_naturezas:
                item.setSelected(True)

    def accept(self):
        nome = self.input_nome.text().strip()
        codigo = self.input_codigo.text().strip()
        
        if not nome or not codigo:
            QMessageBox.warning(self, "Campos Obrigatórios", "Preencha Código e Nome.")
            return

        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        preco_str = self.input_preco.text().strip().replace(',', '.')
        
        dados_produto = {
            "codigo": codigo, "nome": nome, "preco": preco_str if preco_str else "0.00",
            "descricao": self.input_descricao.text(),
            "codigoB": self.input_codigoB.text(), "codigoC": self.input_codigoC.text()
        }

        ids_forn = [self.lista_fornecedores.item(i).data(Qt.UserRole) for i in range(self.lista_fornecedores.count()) if self.lista_fornecedores.item(i).isSelected()]
        ids_nat = [self.lista_naturezas.item(i).data(Qt.UserRole) for i in range(self.lista_naturezas.count()) if self.lista_naturezas.item(i).isSelected()]

        dados_produto['fornecedores_ids'] = ids_forn
        dados_produto['naturezas_ids'] = ids_nat

        try:
            if self.produto_id is None:
                response = requests.post(f"{API_BASE_URL}/api/produtos", headers=headers, json=dados_produto)
                if response.status_code == 201:
                    produto_salvo_id = response.json().get('id_produto_criado')
                    requests.put(f"{API_BASE_URL}/api/produtos/{produto_salvo_id}", headers=headers, json=dados_produto)
                    super().accept()
                else:
                    raise Exception(response.json().get('erro', 'Erro ao criar'))
            else:
                response = requests.put(f"{API_BASE_URL}/api/produtos/{self.produto_id}", headers=headers, json=dados_produto)
                if response.status_code == 200:
                    self.produto_atualizado.emit(self.row, response.json())
                    QMessageBox.information(self, "Sucesso", "Produto atualizado!")
                    super().accept()
                else:
                    raise Exception(response.json().get('erro', 'Erro ao atualizar'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)
        except Exception as e:
            QMessageBox.warning(self, "Erro", f"Falha ao salvar: {e}")

class FormularioFornecedorDialog(QDialog):
    def __init__(self, parent=None, fornecedor_id=None):
        super().__init__(parent)
        self.fornecedor_id = fornecedor_id
        self.setWindowTitle("Novo Fornecedor" if not self.fornecedor_id else "Editar Fornecedor")
        self.layout = QFormLayout(self)
        
        self.input_nome = QLineEdit()
        self.layout.addRow("Nome:", self.input_nome)
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        self.layout.addWidget(self.botoes)
        
        if self.fornecedor_id:
            self.carregar_dados()

    def carregar_dados(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f"{API_BASE_URL}/api/fornecedores/{self.fornecedor_id}", headers=headers)
            if response.status_code == 200:
                self.input_nome.setText(response.json().get('nome'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def accept(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"nome": self.input_nome.text()}
        try:
            if self.fornecedor_id is None:
                r = requests.post(f"{API_BASE_URL}/api/fornecedores", headers=headers, json=dados)
            else:
                r = requests.put(f"{API_BASE_URL}/api/fornecedores/{self.fornecedor_id}", headers=headers, json=dados)
            
            if r.status_code in [200, 201]:
                QMessageBox.information(self, "Sucesso", "Salvo com sucesso!")
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro', 'Erro desconhecido'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

class FormularioNaturezaDialog(QDialog):
    def __init__(self, parent=None, natureza_id=None):
        super().__init__(parent)
        self.natureza_id = natureza_id
        self.setWindowTitle("Nova Natureza" if not self.natureza_id else "Editar Natureza")
        self.layout = QFormLayout(self)
        
        self.input_nome = QLineEdit()
        self.layout.addRow("Nome:", self.input_nome)
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        self.layout.addWidget(self.botoes)
        
        if self.natureza_id:
            self.carregar_dados()

    def carregar_dados(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f"{API_BASE_URL}/api/naturezas/{self.natureza_id}", headers=headers)
            if response.status_code == 200:
                self.input_nome.setText(response.json().get('nome'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def accept(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"nome": self.input_nome.text()}
        try:
            if self.natureza_id is None:
                r = requests.post(f"{API_BASE_URL}/api/naturezas", headers=headers, json=dados)
            else:
                r = requests.put(f"{API_BASE_URL}/api/naturezas/{self.natureza_id}", headers=headers, json=dados)
            
            if r.status_code in [200, 201]:
                QMessageBox.information(self, "Sucesso", "Salvo com sucesso!")
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro', 'Erro desconhecido'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

class QuickAddDialog(QDialog):
    item_adicionado = Signal()

    def __init__(self, parent, titulo, endpoint):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.endpoint = endpoint
        self.setMinimumWidth(300)
        self.layout = QVBoxLayout(self)
        
        self.form_layout = QFormLayout()
        self.input_nome = QLineEdit()
        self.form_layout.addRow("Nome:", self.input_nome)
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.layout.addLayout(self.form_layout)
        self.layout.addWidget(self.botoes)
        
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)

    def accept(self):
        nome = self.input_nome.text().strip()
        if not nome:
            return

        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"nome": nome}
        try:
            response = requests.post(f"{API_BASE_URL}{self.endpoint}", headers=headers, json=dados)
            if response.status_code == 201:
                self.item_adicionado.emit()
                if self.endpoint == "/api/fornecedores":
                    signal_handler.fornecedores_atualizados.emit()
                elif self.endpoint == "/api/naturezas":
                    signal_handler.naturezas_atualizadas.emit()
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", response.json().get('erro', 'Erro'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

class FormularioUsuarioDialog(QDialog):
    def __init__(self, parent=None, usuario_id=None):
        super().__init__(parent)
        self.usuario_id = usuario_id
        self.setWindowTitle("Novo Usuário" if not self.usuario_id else "Editar Usuário")
        self.setMinimumWidth(350)
        
        self.layout = QFormLayout(self)
        self.input_nome = QLineEdit()
        self.input_login = QLineEdit()
        self.input_senha = QLineEdit()
        self.input_senha.setPlaceholderText("Deixe em branco para não alterar")
        
        self.input_permissao = QComboBox()
        self.input_permissao.addItems(["Usuario", "Administrador"])
        
        self.layout.addRow("Nome:", self.input_nome)
        self.layout.addRow("Login:", self.input_login)
        self.layout.addRow("Nova Senha:", self.input_senha)
        self.layout.addRow("Permissão:", self.input_permissao)
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        self.layout.addWidget(self.botoes)
        
        if self.usuario_id:
            self.carregar_dados()

    def carregar_dados(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            response = requests.get(f"{API_BASE_URL}/api/usuarios/{self.usuario_id}", headers=headers)
            if response.status_code == 200:
                dados = response.json()
                self.input_nome.setText(dados.get('nome', ''))
                self.input_login.setText(dados.get('login', ''))
                self.input_permissao.setCurrentText(dados.get('permissao', 'Usuario'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)
            self.reject()

    def accept(self):
        global access_token
        if not self.input_nome.text().strip() or not self.input_login.text().strip():
            QMessageBox.warning(self, "Erro", "Nome e Login obrigatórios.")
            return

        dados = {
            "nome": self.input_nome.text(),
            "login": self.input_login.text(),
            "permissao": self.input_permissao.currentText()
        }
        if self.input_senha.text():
            dados['senha'] = self.input_senha.text()
        elif self.usuario_id is None:
            QMessageBox.warning(self, "Erro", "Senha obrigatória para novos usuários.")
            return

        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            if self.usuario_id is None:
                r = requests.post(f"{API_BASE_URL}/api/usuarios", headers=headers, json=dados)
            else:
                r = requests.put(f"{API_BASE_URL}/api/usuarios/{self.usuario_id}", headers=headers, json=dados)
            
            if r.status_code in [200, 201]:
                QMessageBox.information(self, "Sucesso", "Usuário salvo!")
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro', 'Erro'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

class MudarSenhaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Alterar Senha")
        self.setMinimumWidth(350)
        self.layout = QFormLayout(self)
        self.layout.setSpacing(15)
        
        self.input_senha_atual = QLineEdit()
        self.input_senha_atual.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_nova_senha = QLineEdit()
        self.input_nova_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_confirmacao = QLineEdit()
        self.input_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.layout.addRow("Senha Atual:", self.input_senha_atual)
        self.layout.addRow("Nova Senha:", self.input_nova_senha)
        self.layout.addRow("Confirmar:", self.input_confirmacao)
        
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.botoes)
        
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        self.input_confirmacao.returnPressed.connect(self.accept)

    def accept(self):
        atual = self.input_senha_atual.text()
        nova = self.input_nova_senha.text()
        conf = self.input_confirmacao.text()
        
        if not atual or not nova or not conf:
            QMessageBox.warning(self, "Erro", "Preencha todos os campos.")
            return
        if nova != conf:
            QMessageBox.warning(self, "Erro", "As senhas não coincidem.")
            return

        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"senha_atual": atual, "nova_senha": nova, "confirmacao_nova_senha": conf}
        try:
            r = requests.post(f"{API_BASE_URL}/api/usuario/mudar-senha", headers=headers, json=dados)
            if r.status_code == 200:
                QMessageBox.information(self, "Sucesso", "Senha alterada!")
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro', 'Erro'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

class QuantidadeDialog(QDialog):
    estoque_modificado = Signal(str)

    def __init__(self, parent, produto_id, produto_nome, produto_codigo, operacao):
        super().__init__(parent)
        self.produto_id = produto_id
        self.produto_codigo = produto_codigo
        self.operacao = operacao
        
        titulo = "Adicionar" if operacao == "Entrada" else "Remover"
        self.setWindowTitle(f"{titulo} Estoque")
        self.setMinimumWidth(350)
        
        self.layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.label_produto = QLabel(f"<b>Produto:</b> {produto_nome}")
        self.input_quantidade = QLineEdit()
        self.input_quantidade.setValidator(QDoubleValidator(0, 99999, 0))
        self.input_motivo = QLineEdit()
        
        form_layout.addRow(self.label_produto)
        form_layout.addRow("Quantidade:", self.input_quantidade)
        if self.operacao == "Saida":
            form_layout.addRow("Motivo:", self.input_motivo)
            
        self.botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.layout.addLayout(form_layout)
        self.layout.addWidget(self.botoes)
        
        self.botoes.accepted.connect(self.accept)
        self.botoes.rejected.connect(self.reject)
        self.input_quantidade.setFocus()

    def accept(self):
        qtd_str = self.input_quantidade.text()
        if not qtd_str or int(qtd_str) <= 0:
            return
            
        dados = { "id_produto": self.produto_id, "quantidade": int(qtd_str) }
        endpoint = "/api/estoque/entrada"
        
        if self.operacao == "Saida":
            motivo = self.input_motivo.text().strip()
            if not motivo:
                QMessageBox.warning(self, "Erro", "Motivo obrigatório.")
                return
            dados["motivo_saida"] = motivo
            endpoint = "/api/estoque/saida"
            
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.post(f"{API_BASE_URL}{endpoint}", headers=headers, json=dados)
            if r.status_code == 201:
                self.estoque_modificado.emit(self.produto_codigo)
                super().accept()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro', 'Erro'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

# ==============================================================================
# 4. WIDGETS DE CONTEÚDO
# ==============================================================================

class ImportacaoWidget(QWidget):
    produtos_importados_sucesso = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.caminho_ficheiro = None
        
        titulo = QLabel("Importação de Produtos em Massa")
        titulo.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 10px;")
        
        instrucoes = QLabel(
            "<b>Instruções:</b><br>"
            "1. CSV com colunas: <b>codigo, nome</b> (obrigatórias).<br>"
            "2. Opcionais: <b>preco, quantidade, descricao, fornecedores_nomes, naturezas_nomes</b>.<br>"
            "3. Separe múltiplos nomes com vírgula."
        )
        instrucoes.setWordWrap(True)
        
        layout_selecao = QHBoxLayout()
        self.btn_selecionar = QPushButton("📂 Selecionar CSV...")
        self.label_ficheiro = QLabel("Nenhum ficheiro selecionado.")
        
        layout_selecao.addWidget(self.btn_selecionar)
        layout_selecao.addWidget(self.label_ficheiro)
        layout_selecao.addStretch(1)
        
        self.btn_importar = QPushButton("🚀 Iniciar Importação")
        self.btn_importar.setObjectName("btnPositive")
        self.btn_importar.setEnabled(False)
        
        self.text_resultados = QTextEdit()
        self.text_resultados.setReadOnly(True)
        
        self.layout.addWidget(titulo)
        self.layout.addWidget(instrucoes)
        self.layout.addLayout(layout_selecao)
        self.layout.addWidget(self.btn_importar)
        self.layout.addWidget(QLabel("Resultados:"))
        self.layout.addWidget(self.text_resultados)
        
        self.btn_selecionar.clicked.connect(self.selecionar_ficheiro)
        self.btn_importar.clicked.connect(self.iniciar_importacao)

    def selecionar_ficheiro(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar CSV", "", "CSV (*.csv)")
        if caminho:
            self.caminho_ficheiro = caminho
            self.label_ficheiro.setText(os.path.basename(caminho))
            self.btn_importar.setEnabled(True)
            self.text_resultados.clear()

    def iniciar_importacao(self):
        if not self.caminho_ficheiro:
            return

        self.text_resultados.setText("A importar...")
        QApplication.processEvents()
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            with open(self.caminho_ficheiro, 'rb') as f:
                files = {'file': (os.path.basename(self.caminho_ficheiro), f, 'text/csv')}
                response = requests.post(f"{API_BASE_URL}/api/produtos/importar", headers=headers, files=files)
            
            if response.status_code == 200:
                dados = response.json()
                texto = f"{dados.get('mensagem', '')}\n"
                texto += f"Sucesso: {dados.get('produtos_importados', 0)}\n\n"
                
                if dados.get('erros'):
                    texto += "Erros:\n" + "\n".join(dados['erros'])
                
                self.text_resultados.setText(texto)
                if dados.get('produtos_importados', 0) > 0:
                    self.produtos_importados_sucesso.emit()
            else:
                self.text_resultados.setText(f"Erro na API: {response.text}")
        except requests.exceptions.RequestException:
            show_connection_error_message(self)
        except Exception as e:
            self.text_resultados.setText(f"Erro crítico: {e}")
        
        self.btn_importar.setEnabled(False)

class InventarioWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.dados_exibidos = []
        self.sort_qtd_desc = True
        
        self.titulo = QLabel("Inventário Completo")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        controles_1 = QHBoxLayout()
        self.input_pesquisa = QLineEdit()
        self.input_pesquisa.setPlaceholderText("Buscar por Nome ou Código...")
        controles_1.addWidget(self.input_pesquisa)
        
        controles_2 = QHBoxLayout()
        self.btn_adicionar = QPushButton("➕ Adicionar")
        self.btn_adicionar.setObjectName("btnPositive")
        self.btn_editar = QPushButton("✏️ Editar")
        self.btn_editar.setObjectName("btnNeutral")
        self.btn_excluir = QPushButton("🗑️ Excluir")
        self.btn_excluir.setObjectName("btnNegative")
        self.btn_etiquetas = QPushButton("🖨️ Etiquetas")
        self.btn_etiquetas.setObjectName("btnPrint")
        
        controles_2.addWidget(self.btn_adicionar)
        controles_2.addWidget(self.btn_editar)
        controles_2.addWidget(self.btn_excluir)
        controles_2.addWidget(self.btn_etiquetas)
        controles_2.addStretch(1)
        
        self.btn_ordenar_nome = QPushButton("🔤 A-Z")
        self.btn_ordenar_qtd = QPushButton("📦 Qtd.")
        controles_2.addWidget(self.btn_ordenar_nome)
        controles_2.addWidget(self.btn_ordenar_qtd)
        
        self.tabela = QTableWidget()
        self.tabela.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tabela.setColumnCount(7)
        self.tabela.setHorizontalHeaderLabels(["Código", "Nome", "Descrição", "Saldo", "Preço", "Cód B", "Cód C"])
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setAlternatingRowColors(True)
        
        header = self.tabela.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(controles_1)
        self.layout.addLayout(controles_2)
        self.layout.addWidget(self.tabela)
        
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.carregar_dados_inventario)
        self.input_pesquisa.textChanged.connect(self.iniciar_busca_timer)
        
        self.btn_adicionar.clicked.connect(self.abrir_formulario_adicionar)
        self.btn_editar.clicked.connect(self.abrir_formulario_editar)
        self.btn_excluir.clicked.connect(self.excluir_produto_selecionado)
        self.btn_etiquetas.clicked.connect(self.gerar_etiquetas_selecionadas)
        self.btn_ordenar_nome.clicked.connect(self.ordenar_por_nome)
        self.btn_ordenar_qtd.clicked.connect(self.ordenar_por_quantidade)
        
        self.carregar_dados_inventario()

    def iniciar_busca_timer(self):
        self.search_timer.stop()
        self.search_timer.start(300)

    def carregar_dados_inventario(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        params = {}
        if self.input_pesquisa.text():
            params['search'] = self.input_pesquisa.text()

        try:
            response = requests.get(f"{API_BASE_URL}/api/estoque/saldos", headers=headers, params=params)
            if response.status_code == 200:
                self.dados_exibidos = response.json()
                self.popular_tabela(self.dados_exibidos)
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def popular_tabela(self, dados):
        self.tabela.setRowCount(len(dados))
        for linha, item in enumerate(dados):
            item_codigo = QTableWidgetItem(item['codigo'])
            item_codigo.setData(Qt.UserRole, item['id_produto'])
            
            self.tabela.setItem(linha, 0, item_codigo)
            self.tabela.setItem(linha, 1, QTableWidgetItem(item['nome']))
            self.tabela.setItem(linha, 2, QTableWidgetItem(item.get('descricao', '')))
            
            saldo = QTableWidgetItem(str(item['saldo_atual']))
            saldo.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabela.setItem(linha, 3, saldo)
            
            preco = QTableWidgetItem(str(item.get('preco', '0.00')))
            preco.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.tabela.setItem(linha, 4, preco)
            
            self.tabela.setItem(linha, 5, QTableWidgetItem(item.get('codigoB', '')))
            self.tabela.setItem(linha, 6, QTableWidgetItem(item.get('codigoC', '')))
        
        self.tabela.resizeRowsToContents()

    def ordenar_por_nome(self):
        self.dados_exibidos.sort(key=lambda x: x['nome'].lower())
        self.popular_tabela(self.dados_exibidos)

    def ordenar_por_quantidade(self):
        self.dados_exibidos.sort(key=lambda x: int(x['saldo_atual']), reverse=self.sort_qtd_desc)
        self.sort_qtd_desc = not self.sort_qtd_desc
        self.popular_tabela(self.dados_exibidos)

    def abrir_formulario_adicionar(self):
        if FormularioProdutoDialog(self).exec():
            self.carregar_dados_inventario()

    def abrir_formulario_editar(self):
        row = self.tabela.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Atenção", "Selecione um produto.")
            return
        
        produto_id = self.tabela.item(row, 0).data(Qt.UserRole)
        dialog = FormularioProdutoDialog(self, produto_id=produto_id, row=row)
        dialog.produto_atualizado.connect(self.carregar_dados_inventario)
        dialog.exec()

    def excluir_produto_selecionado(self):
        row = self.tabela.currentRow()
        if row < 0:
            return
            
        produto_id = self.tabela.item(row, 0).data(Qt.UserRole)
        nome = self.tabela.item(row, 1).text()
        
        if QMessageBox.question(self, "Excluir", f"Excluir '{nome}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            global access_token
            headers = {'Authorization': f'Bearer {access_token}'}
            try:
                requests.delete(f"{API_BASE_URL}/api/produtos/{produto_id}", headers=headers)
                self.carregar_dados_inventario()
            except requests.exceptions.RequestException:
                show_connection_error_message(self)

    def gerar_etiquetas_selecionadas(self):
        rows = self.tabela.selectionModel().selectedRows()
        if not rows:
            return
            
        ids = [self.tabela.item(r.row(), 0).data(Qt.UserRole) for r in rows]
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Etiquetas", "etiquetas.pdf", "PDF (*.pdf)")
        
        if path:
            global access_token
            headers = {'Authorization': f'Bearer {access_token}'}
            try:
                response = requests.post(f"{API_BASE_URL}/api/produtos/etiquetas", headers=headers, json={'product_ids': ids}, stream=True)
                if response.status_code == 200:
                    with open(path, 'wb') as f:
                        for chunk in response.iter_content(8192):
                            f.write(chunk)
                    QMessageBox.information(self, "Sucesso", "Etiquetas geradas!")
            except requests.exceptions.RequestException:
                show_connection_error_message(self)

class GestaoEstoqueWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0,0,0,0)
        
        self.inventario_view = InventarioWidget()
        self.historico_view = HistoricoWidget()
        
        nav_layout = QHBoxLayout()
        self.btn_ver_inventario = QPushButton("Visão Geral")
        self.btn_ver_historico = QPushButton("Histórico")
        self.btn_ver_inventario.setCheckable(True)
        self.btn_ver_historico.setCheckable(True)
        self.btn_ver_inventario.setChecked(True)
        
        nav_layout.addWidget(self.btn_ver_inventario)
        nav_layout.addWidget(self.btn_ver_historico)
        nav_layout.addStretch(1)
        
        self.stack = QStackedWidget()
        self.stack.addWidget(self.inventario_view)
        self.stack.addWidget(self.historico_view)
        
        self.layout.addLayout(nav_layout)
        self.layout.addWidget(self.stack)
        
        self.btn_ver_inventario.clicked.connect(self.mostrar_inventario)
        self.btn_ver_historico.clicked.connect(self.mostrar_historico)

    def mostrar_inventario(self):
        self.stack.setCurrentWidget(self.inventario_view)
        self.btn_ver_inventario.setChecked(True)
        self.btn_ver_historico.setChecked(False)
        self.inventario_view.carregar_dados_inventario()

    def mostrar_historico(self):
        self.stack.setCurrentWidget(self.historico_view)
        self.btn_ver_inventario.setChecked(False)
        self.btn_ver_historico.setChecked(True)
        self.historico_view.carregar_historico()

class HistoricoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        
        filtros = QHBoxLayout()
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Todas", "Entrada", "Saida"])
        self.btn_recarregar = QPushButton("Atualizar")
        
        filtros.addWidget(QLabel("Filtrar:"))
        filtros.addWidget(self.combo_tipo)
        filtros.addStretch(1)
        filtros.addWidget(self.btn_recarregar)
        
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(8)
        self.tabela.setHorizontalHeaderLabels(["Data", "Cód", "Produto", "Tipo", "Qtd", "Saldo Após", "Usuário", "Motivo"])
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        self.layout.addLayout(filtros)
        self.layout.addWidget(self.tabela)
        
        self.btn_recarregar.clicked.connect(self.carregar_historico)
        self.combo_tipo.currentIndexChanged.connect(self.carregar_historico)
        self.carregar_historico()

    def carregar_historico(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        fim = QDate.currentDate()
        inicio = fim.addDays(-90)
        
        params = {
            'data_inicio': inicio.toString("yyyy-MM-dd"),
            'data_fim': fim.toString("yyyy-MM-dd"),
            'formato': 'json'
        }
        
        if self.combo_tipo.currentText() != "Todas":
            params['tipo'] = self.combo_tipo.currentText()

        try:
            response = requests.get(f"{API_BASE_URL}/api/relatorios/movimentacoes", headers=headers, params=params)
            if response.status_code == 200:
                self.popular_tabela(response.json())
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def popular_tabela(self, dados):
        self.tabela.setRowCount(len(dados))
        for linha, mov in enumerate(dados):
            self.tabela.setItem(linha, 0, QTableWidgetItem(mov['data_hora']))
            self.tabela.setItem(linha, 1, QTableWidgetItem(mov['produto_codigo']))
            self.tabela.setItem(linha, 2, QTableWidgetItem(mov['produto_nome']))
            self.tabela.setItem(linha, 3, QTableWidgetItem(mov['tipo']))
            self.tabela.setItem(linha, 4, QTableWidgetItem(str(mov['quantidade'])))
            self.tabela.setItem(linha, 5, QTableWidgetItem(str(mov.get('saldo_apos', ''))))
            self.tabela.setItem(linha, 6, QTableWidgetItem(mov['usuario_nome']))
            self.tabela.setItem(linha, 7, QTableWidgetItem(mov.get('motivo_saida', '')))

class RelatoriosWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        titulo = QLabel("Gerador de Relatórios")
        titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        form = QFormLayout()
        self.combo_relatorio = QComboBox()
        self.combo_relatorio.addItems(["Inventário Atual", "Histórico de Movimentações"])
        
        self.data_inicio = QDateEdit(QDate.currentDate().addMonths(-1))
        self.data_inicio.setCalendarPopup(True)
        self.data_fim = QDateEdit(QDate.currentDate())
        self.data_fim.setCalendarPopup(True)
        
        self.combo_mov = QComboBox()
        self.combo_mov.addItems(["Todas", "Entrada", "Saida"])
        
        form.addRow("Tipo:", self.combo_relatorio)
        form.addRow("Início:", self.data_inicio)
        form.addRow("Fim:", self.data_fim)
        form.addRow("Movimentação:", self.combo_mov)
        
        botoes = QHBoxLayout()
        self.btn_pdf = QPushButton("PDF")
        self.btn_excel = QPushButton("Excel")
        botoes.addWidget(self.btn_pdf)
        botoes.addWidget(self.btn_excel)
        
        self.layout.addWidget(titulo)
        self.layout.addLayout(form)
        self.layout.addLayout(botoes)
        
        self.combo_relatorio.currentIndexChanged.connect(self.atualizar_filtros)
        self.btn_pdf.clicked.connect(lambda: self.gerar('pdf'))
        self.btn_excel.clicked.connect(lambda: self.gerar('xlsx'))
        self.atualizar_filtros()

    def atualizar_filtros(self):
        visivel = (self.combo_relatorio.currentText() == "Histórico de Movimentações")
        self.data_inicio.setVisible(visivel)
        self.data_fim.setVisible(visivel)
        self.combo_mov.setVisible(visivel)

    def gerar(self, ext):
        endpoint = "/api/relatorios/inventario" if self.combo_relatorio.currentText() == "Inventário Atual" else "/api/relatorios/movimentacoes"
        params = {'formato': ext}
        
        if "movimentacoes" in endpoint:
            params['data_inicio'] = self.data_inicio.date().toString("yyyy-MM-dd")
            params['data_fim'] = self.data_fim.date().toString("yyyy-MM-dd")
            if self.combo_mov.currentText() != "Todas":
                params['tipo'] = self.combo_mov.currentText()
        
        path, _ = QFileDialog.getSaveFileName(self, "Salvar", f"relatorio.{ext}", f"Arquivos (*.{ext})")
        if path:
            global access_token
            headers = {'Authorization': f'Bearer {access_token}'}
            try:
                r = requests.get(f"{API_BASE_URL}{endpoint}", headers=headers, params=params, stream=True)
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        for chunk in r.iter_content(8192):
                            f.write(chunk)
                    QMessageBox.information(self, "Sucesso", "Relatório salvo!")
            except requests.exceptions.RequestException:
                show_connection_error_message(self)

class FornecedoresWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.titulo = QLabel("Fornecedores")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        botoes = QHBoxLayout()
        self.btn_add = QPushButton("➕ Adicionar")
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_del = QPushButton("🗑️ Excluir")
        botoes.addWidget(self.btn_add)
        botoes.addWidget(self.btn_edit)
        botoes.addWidget(self.btn_del)
        botoes.addStretch(1)
        
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(1)
        self.tabela.setHorizontalHeaderLabels(["Nome"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(botoes)
        self.layout.addWidget(self.tabela)
        
        self.btn_add.clicked.connect(self.add)
        self.btn_edit.clicked.connect(self.edit)
        self.btn_del.clicked.connect(self.delete)
        self.carregar()

    def carregar(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/fornecedores", headers=headers)
            if r.status_code == 200:
                dados = r.json()
                self.tabela.setRowCount(len(dados))
                for i, f in enumerate(dados):
                    item = QTableWidgetItem(f['nome'])
                    item.setData(Qt.UserRole, f['id'])
                    self.tabela.setItem(i, 0, item)
        except requests.exceptions.RequestException:
            pass

    def add(self):
        if FormularioFornecedorDialog(self).exec():
            self.carregar()

    def edit(self):
        row = self.tabela.currentRow()
        if row >= 0:
            fid = self.tabela.item(row, 0).data(Qt.UserRole)
            if FormularioFornecedorDialog(self, fid).exec():
                self.carregar()

    def delete(self):
        row = self.tabela.currentRow()
        if row >= 0:
            fid = self.tabela.item(row, 0).data(Qt.UserRole)
            if QMessageBox.question(self, "Excluir", "Confirmar exclusão?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                global access_token
                headers = {'Authorization': f'Bearer {access_token}'}
                requests.delete(f"{API_BASE_URL}/api/fornecedores/{fid}", headers=headers)
                self.carregar()

class NaturezasWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.titulo = QLabel("Naturezas")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        botoes = QHBoxLayout()
        self.btn_add = QPushButton("➕ Adicionar")
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_del = QPushButton("🗑️ Excluir")
        botoes.addWidget(self.btn_add)
        botoes.addWidget(self.btn_edit)
        botoes.addWidget(self.btn_del)
        botoes.addStretch(1)
        
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(1)
        self.tabela.setHorizontalHeaderLabels(["Nome"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(botoes)
        self.layout.addWidget(self.tabela)
        
        self.btn_add.clicked.connect(self.add)
        self.btn_edit.clicked.connect(self.edit)
        self.btn_del.clicked.connect(self.delete)
        self.carregar_naturezas()

    def carregar_naturezas(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/naturezas", headers=headers)
            if r.status_code == 200:
                dados = r.json()
                self.tabela.setRowCount(len(dados))
                for i, n in enumerate(dados):
                    item = QTableWidgetItem(n['nome'])
                    item.setData(Qt.UserRole, n['id'])
                    self.tabela.setItem(i, 0, item)
        except requests.exceptions.RequestException:
            pass

    def add(self):
        if FormularioNaturezaDialog(self).exec():
            self.carregar_naturezas()

    def edit(self):
        row = self.tabela.currentRow()
        if row >= 0:
            nid = self.tabela.item(row, 0).data(Qt.UserRole)
            if FormularioNaturezaDialog(self, nid).exec():
                self.carregar_naturezas()

    def delete(self):
        row = self.tabela.currentRow()
        if row >= 0:
            nid = self.tabela.item(row, 0).data(Qt.UserRole)
            if QMessageBox.question(self, "Excluir", "Confirmar exclusão?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                global access_token
                headers = {'Authorization': f'Bearer {access_token}'}
                requests.delete(f"{API_BASE_URL}/api/naturezas/{nid}", headers=headers)
                self.carregar_naturezas()

class EntradaRapidaWidget(QWidget):
    estoque_atualizado = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.produto_encontrado_id = None
        
        self.titulo = QLabel("Entrada Rápida")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        form = QFormLayout()
        self.input_codigo = QLineEdit()
        self.input_codigo.setPlaceholderText("Código...")
        self.btn_verificar = QPushButton("Buscar")
        
        linha_cod = QHBoxLayout()
        linha_cod.addWidget(self.input_codigo)
        linha_cod.addWidget(self.btn_verificar)
        
        self.label_nome = QLabel("Aguardando...")
        self.input_qtd = QLineEdit()
        self.input_qtd.setPlaceholderText("Qtd")
        self.input_qtd.setValidator(QDoubleValidator(0, 99999, 0))
        
        self.btn_salvar = QPushButton("Registrar Entrada")
        self.btn_salvar.setObjectName("btnPositive")
        
        form.addRow("Código:", linha_cod)
        form.addRow("Produto:", self.label_nome)
        form.addRow("Qtd:", self.input_qtd)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(form)
        self.layout.addWidget(self.btn_salvar)
        self.layout.addStretch(1)
        
        self.btn_verificar.clicked.connect(self.verificar)
        self.input_codigo.returnPressed.connect(self.verificar)
        self.btn_salvar.clicked.connect(self.salvar)
        self.input_qtd.returnPressed.connect(self.salvar)
        self.resetar()

    def verificar(self):
        cod = self.input_codigo.text().strip()
        if not cod: return
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/produtos/codigo/{cod}", headers=headers)
            if r.status_code == 200:
                data = r.json()
                self.produto_encontrado_id = data['id']
                self.label_nome.setText(data['nome'])
                self.label_nome.setStyleSheet("color: green; font-weight: bold;")
                self.input_qtd.setEnabled(True)
                self.btn_salvar.setEnabled(True)
                self.input_qtd.setFocus()
            else:
                self.label_nome.setText("Não encontrado")
                self.label_nome.setStyleSheet("color: red;")
                self.produto_encontrado_id = None
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def salvar(self):
        qtd = self.input_qtd.text()
        if not self.produto_encontrado_id or not qtd: return
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"id_produto": self.produto_encontrado_id, "quantidade": int(qtd)}
        
        try:
            r = requests.post(f"{API_BASE_URL}/api/estoque/entrada", headers=headers, json=dados)
            if r.status_code == 201:
                self.estoque_atualizado.emit()
                QMessageBox.information(self, "Sucesso", "Entrada registrada!")
                self.resetar()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro'))
        except requests.exceptions.RequestException:
            show_connection_error_message(self)

    def resetar(self):
        self.produto_encontrado_id = None
        self.input_codigo.clear()
        self.input_qtd.clear()
        self.label_nome.setText("Aguardando...")
        self.input_qtd.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.input_codigo.setFocus()

class SaidaRapidaWidget(QWidget):
    estoque_atualizado = Signal()

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.produto_encontrado_id = None
        
        self.titulo = QLabel("Saída Rápida")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        form = QFormLayout()
        self.input_codigo = QLineEdit()
        self.btn_verificar = QPushButton("Buscar")
        
        linha_cod = QHBoxLayout()
        linha_cod.addWidget(self.input_codigo)
        linha_cod.addWidget(self.btn_verificar)
        
        self.label_nome = QLabel("Aguardando...")
        self.input_qtd = QLineEdit()
        self.input_motivo = QLineEdit()
        self.input_motivo.setPlaceholderText("Ex: Venda")
        
        self.btn_salvar = QPushButton("Registrar Saída")
        self.btn_salvar.setObjectName("btnNegative")
        
        form.addRow("Código:", linha_cod)
        form.addRow("Produto:", self.label_nome)
        form.addRow("Qtd:", self.input_qtd)
        form.addRow("Motivo:", self.input_motivo)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(form)
        self.layout.addWidget(self.btn_salvar)
        self.layout.addStretch(1)
        
        self.btn_verificar.clicked.connect(self.verificar)
        self.input_codigo.returnPressed.connect(self.verificar)
        self.btn_salvar.clicked.connect(self.salvar)
        self.input_motivo.returnPressed.connect(self.salvar)
        self.resetar()

    def verificar(self):
        cod = self.input_codigo.text().strip()
        if not cod: return
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/produtos/codigo/{cod}", headers=headers)
            if r.status_code == 200:
                data = r.json()
                self.produto_encontrado_id = data['id']
                self.label_nome.setText(data['nome'])
                self.label_nome.setStyleSheet("color: green; font-weight: bold;")
                self.input_qtd.setEnabled(True)
                self.input_motivo.setEnabled(True)
                self.btn_salvar.setEnabled(True)
                self.input_qtd.setFocus()
            else:
                self.label_nome.setText("Não encontrado")
                self.produto_encontrado_id = None
        except requests.exceptions.RequestException:
            pass

    def salvar(self):
        qtd = self.input_qtd.text()
        motivo = self.input_motivo.text()
        if not self.produto_encontrado_id or not qtd or not motivo: return
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        dados = {"id_produto": self.produto_encontrado_id, "quantidade": int(qtd), "motivo_saida": motivo}
        
        try:
            r = requests.post(f"{API_BASE_URL}/api/estoque/saida", headers=headers, json=dados)
            if r.status_code == 201:
                self.estoque_atualizado.emit()
                QMessageBox.information(self, "Sucesso", "Saída registrada!")
                self.resetar()
            else:
                QMessageBox.warning(self, "Erro", r.json().get('erro'))
        except requests.exceptions.RequestException:
            pass

    def resetar(self):
        self.produto_encontrado_id = None
        self.input_codigo.clear()
        self.input_qtd.clear()
        self.input_motivo.clear()
        self.label_nome.setText("Aguardando...")
        self.input_qtd.setEnabled(False)
        self.input_motivo.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.input_codigo.setFocus()

class UsuariosWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout(self)
        self.titulo = QLabel("Usuários")
        self.titulo.setStyleSheet("font-size: 24px; font-weight: bold;")
        
        botoes = QHBoxLayout()
        self.btn_add = QPushButton("➕ Novo")
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_status = QPushButton("🚫 Ativar/Desativar")
        botoes.addWidget(self.btn_add)
        botoes.addWidget(self.btn_edit)
        botoes.addWidget(self.btn_status)
        botoes.addStretch(1)
        
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(["Nome", "Login", "Permissão", "Status"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.layout.addWidget(self.titulo)
        self.layout.addLayout(botoes)
        self.layout.addWidget(self.tabela)
        
        self.btn_add.clicked.connect(self.add)
        self.btn_edit.clicked.connect(self.edit)
        self.btn_status.clicked.connect(self.toggle_status)
        self.carregar()

    def carregar(self):
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/usuarios", headers=headers)
            if r.status_code == 200:
                dados = r.json()
                self.tabela.setRowCount(len(dados))
                for i, u in enumerate(dados):
                    item = QTableWidgetItem(u['nome'])
                    item.setData(Qt.UserRole, u['id'])
                    self.tabela.setItem(i, 0, item)
                    self.tabela.setItem(i, 1, QTableWidgetItem(u['login']))
                    self.tabela.setItem(i, 2, QTableWidgetItem(u['permissao']))
                    self.tabela.setItem(i, 3, QTableWidgetItem("Ativo" if u['ativo'] else "Inativo"))
        except requests.exceptions.RequestException:
            pass

    def add(self):
        if FormularioUsuarioDialog(self).exec():
            self.carregar()

    def edit(self):
        row = self.tabela.currentRow()
        if row >= 0:
            uid = self.tabela.item(row, 0).data(Qt.UserRole)
            if FormularioUsuarioDialog(self, uid).exec():
                self.carregar()

    def toggle_status(self):
        row = self.tabela.currentRow()
        if row >= 0:
            uid = self.tabela.item(row, 0).data(Qt.UserRole)
            if QMessageBox.question(self, "Confirmar", "Alterar status do usuário?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
                global access_token
                headers = {'Authorization': f'Bearer {access_token}'}
                requests.delete(f"{API_BASE_URL}/api/usuarios/{uid}", headers=headers)
                self.carregar()

class TerminalWidget(QWidget):
    ir_para_novo_produto = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("terminalWidget")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 10, 20, 20)
        
        self.barcode_buffer = ""
        self.barcode_timer = QTimer(self)
        self.barcode_timer.setSingleShot(True)
        self.barcode_timer.setInterval(200)
        self.produto_atual = None
        
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QPixmap(resource_path("logo.png")).scaled(200, 80, Qt.AspectRatioMode.KeepAspectRatio))
        titulo = QLabel("SUPER TERMINAL")
        titulo.setObjectName("terminalHeaderTitle")
        self.btn_novo = QPushButton("➕ Novo Produto")
        self.btn_novo.setObjectName("btnTerminalNewProduct")
        
        header.addWidget(logo)
        header.addStretch(1)
        header.addWidget(titulo)
        header.addStretch(1)
        header.addWidget(self.btn_novo)
        
        main_panel = QFrame()
        main_panel.setObjectName("terminalMainPanel")
        main_layout = QHBoxLayout(main_panel)
        
        self.label_nome = QLabel("Passe o código de barras...")
        self.label_nome.setObjectName("terminalProductName")
        self.label_nome.setWordWrap(True)
        
        qtd_box = QFrame()
        qtd_box.setObjectName("terminalQuantityBox")
        qtd_layout = QVBoxLayout(qtd_box)
        self.label_qtd = QLabel("--")
        self.label_qtd.setObjectName("terminalQuantityValue")
        qtd_layout.addWidget(self.label_qtd)
        
        main_layout.addWidget(self.label_nome, 3)
        main_layout.addWidget(qtd_box, 1)
        
        bottom = QFrame()
        bottom.setObjectName("terminalBottomPanel")
        bottom_layout = QHBoxLayout(bottom)
        
        info_layout = QVBoxLayout()
        self.label_desc = QLabel("Descrição aqui.")
        self.label_code = QLabel("Código: --")
        info_layout.addWidget(self.label_desc)
        info_layout.addWidget(self.label_code)
        
        actions = QHBoxLayout()
        self.btn_rem = QPushButton("➖")
        self.btn_add = QPushButton("➕")
        actions.addWidget(self.btn_rem)
        actions.addWidget(self.btn_add)
        
        bottom_layout.addLayout(info_layout, 3)
        bottom_layout.addLayout(actions, 1)
        
        self.layout.addLayout(header)
        self.layout.addWidget(main_panel, 1)
        self.layout.addWidget(bottom, 1)
        
        self.barcode_timer.timeout.connect(self.processar_codigo)
        self.btn_add.clicked.connect(lambda: self.dialogo_qtd("Entrada"))
        self.btn_rem.clicked.connect(lambda: self.dialogo_qtd("Saida"))
        self.btn_novo.clicked.connect(self.ir_para_novo_produto.emit)
        
        self.resetar_tela()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.barcode_timer.stop()
            self.processar_codigo()
        else:
            self.barcode_buffer += event.text()
            self.barcode_timer.start()

    def processar_codigo(self):
        cod = self.barcode_buffer.strip()
        self.barcode_buffer = ""
        if not cod: return
        
        self.label_nome.setText("Buscando...")
        QApplication.processEvents()
        
        global access_token
        headers = {'Authorization': f'Bearer {access_token}'}
        try:
            r = requests.get(f"{API_BASE_URL}/api/estoque/saldos?search={cod}", headers=headers)
            if r.status_code == 200 and r.json():
                self.produto_atual = r.json()[0]
                self.atualizar_display()
            else:
                self.produto_nao_encontrado()
        except:
            self.produto_nao_encontrado()

    def atualizar_display(self):
        p = self.produto_atual
        self.label_nome.setText(p['nome'])
        self.label_qtd.setText(str(p['saldo_atual']))
        self.label_desc.setText(p.get('descricao', ''))
        self.label_code.setText(f"Código: {p['codigo']}")
        self.btn_add.setEnabled(True)
        self.btn_rem.setEnabled(True)

    def produto_nao_encontrado(self):
        self.produto_atual = None
        self.label_nome.setText("Não encontrado.")
        self.resetar_tela(True)

    def resetar_tela(self, manter_msg=False):
        if not manter_msg: self.label_nome.setText("Leitor pronto...")
        self.label_qtd.setText("--")
        self.label_desc.setText("")
        self.label_code.setText("Código: --")
        self.btn_add.setEnabled(False)
        self.btn_rem.setEnabled(False)

    def dialogo_qtd(self, op):
        if not self.produto_atual: return
        d = QuantidadeDialog(self, self.produto_atual['id_produto'], self.produto_atual['nome'], self.produto_atual['codigo'], op)
        d.estoque_modificado.connect(self.reprocessar)
        d.exec()

    def reprocessar(self, cod):
        self.barcode_buffer = cod
        self.processar_codigo()

# ==============================================================================
# CLASSES DE DOCUMENTOS 
# ==============================================================================

class DocumentacaoWidget(QWidget):
    def __init__(self, servico_id):
        super().__init__()
        self.servico_id = servico_id
        self.dados_form = {}
        
        self.layout_princ = QHBoxLayout(self)
        self.stack = QStackedWidget()
        
        # Tela Formulário
        self.widget_form = QWidget()
        l_form = QVBoxLayout(self.widget_form)
        self.tabs = QTabWidget()
        
        self.tabs.addTab(self._tab_identificacao(), "1. ID")
        self.tabs.addTab(self._tab_escopo(), "2. Escopo")
        self.tabs.addTab(self._tab_docs(), "3. Docs")
        self.tabs.addTab(self._tab_diagramas(), "4. Diagramas")
        self.tabs.addTab(self._tab_instrumentos(), "5. Instrumentos")
        self.tabs.addTab(self._tab_programacao(), "7. Prog")
        self.tabs.addTab(self._tab_testes(), "8. Testes")
        self.tabs.addTab(self._tab_operacao(), "9. Operação")
        self.tabs.addTab(self._tab_treino(), "10. Treino")
        self.tabs.addTab(self._tab_asbuilt(), "11. As Built")
        self.tabs.addTab(self._tab_anexos(), "12. Anexos")
        
        self.btn_prox = QPushButton("Próximo -> Anexos")
        self.btn_prox.clicked.connect(self.ir_anexos)
        l_form.addWidget(self.tabs)
        l_form.addWidget(self.btn_prox)
        
        # Tela Anexos
        self.widget_anexos = AnexosWidget()
        self.widget_anexos.voltar_solicitado.connect(lambda: self.stack.setCurrentWidget(self.widget_form))
        self.widget_anexos.gerar_documento_solicitado.connect(self.gerar_final)
        
        self.stack.addWidget(self.widget_form)
        self.stack.addWidget(self.widget_anexos)
        
        # Painel Lateral (Histórico)
        self.lista_hist = QListWidget()
        self.lista_hist.itemClicked.connect(self.ver_detalhes)
        self.btn_del_hist = QPushButton("Excluir Selecionado")
        self.btn_del_hist.clicked.connect(self.excluir_historico)
        
        l_dir = QVBoxLayout()
        l_dir.addWidget(self.lista_hist)
        l_dir.addWidget(self.btn_del_hist)
        
        self.layout_princ.addWidget(self.stack, 2)
        self.layout_princ.addLayout(l_dir, 1)
        self.carregar_historico()

    # Métodos auxiliares de UI (simplificados)
    def _tab_identificacao(self):
        w = QWidget()
        f = QFormLayout(w)
        self.in_nome = QLineEdit()
        self.in_cli = QLineEdit()
        self.in_loc = QLineEdit()
        self.in_emp = QLineEdit()
        self.in_dat = QLineEdit()
        self.in_con = QLineEdit()
        f.addRow("Projeto:", self.in_nome)
        f.addRow("Cliente:", self.in_cli)
        f.addRow("Local:", self.in_loc)
        f.addRow("Empresa:", self.in_emp)
        f.addRow("Data/Ver:", self.in_dat)
        f.addRow("Contrato:", self.in_con)
        return w

    def _tab_escopo(self):
        w = QWidget()
        f = QFormLayout(w)
        self.txt_obj = QTextEdit()
        self.txt_lim = QTextEdit()
        self.txt_prem = QTextEdit()
        self.txt_int = QTextEdit()
        f.addRow("Objetivos:", self.txt_obj)
        f.addRow("Limites:", self.txt_lim)
        f.addRow("Premissas:", self.txt_prem)
        f.addRow("Interfaces:", self.txt_int)
        return w

    def _tab_docs(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.tab_docs = QTableWidget(0, 6)
        self.tab_docs.setHorizontalHeaderLabels(["Título", "Cód", "Rev", "Data", "Autor", "Status"])
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: self.tab_docs.insertRow(self.tab_docs.rowCount()))
        l.addWidget(self.tab_docs)
        l.addWidget(btn_add)
        return w

    def _tab_diagramas(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.txt_diag = QTextEdit()
        l.addWidget(QLabel("Notas Diagramas:"))
        l.addWidget(self.txt_diag)
        return w

    def _tab_instrumentos(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.tab_inst = QTableWidget(0, 6)
        self.tab_inst.setHorizontalHeaderLabels(["Tag", "Desc", "Fabr", "Faixa", "Sinal", "Local"])
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: self.tab_inst.insertRow(self.tab_inst.rowCount()))
        l.addWidget(self.tab_inst)
        l.addWidget(btn_add)
        return w

    def _tab_programacao(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.tab_prog = QTableWidget(0, 2)
        self.tab_prog.setHorizontalHeaderLabels(["Arquivo", "Desc"])
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: self.tab_prog.insertRow(self.tab_prog.rowCount()))
        l.addWidget(self.tab_prog)
        l.addWidget(btn_add)
        return w

    def _tab_testes(self):
        w = QWidget()
        f = QFormLayout(w)
        self.txt_proc = QTextEdit()
        self.txt_rel = QTextEdit()
        self.txt_nc = QTextEdit()
        f.addRow("Procedimentos:", self.txt_proc)
        f.addRow("Relatórios:", self.txt_rel)
        f.addRow("NCs:", self.txt_nc)
        return w

    def _tab_operacao(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.rad_txt = QRadioButton("Texto")
        self.rad_pdf = QRadioButton("PDF")
        self.rad_txt.setChecked(True)
        self.txt_man = QTextEdit()
        self.in_pdf_man = QLineEdit()
        self.txt_manut = QTextEdit()
        self.txt_sobr = QTextEdit()
        l.addWidget(self.rad_txt)
        l.addWidget(self.rad_pdf)
        l.addWidget(self.txt_man)
        l.addWidget(self.in_pdf_man)
        l.addWidget(QLabel("Manutenção:"))
        l.addWidget(self.txt_manut)
        l.addWidget(QLabel("Sobressalentes:"))
        l.addWidget(self.txt_sobr)
        return w

    def _tab_treino(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.txt_treino = QTextEdit()
        self.tab_part = QTableWidget(0, 2)
        self.tab_part.setHorizontalHeaderLabels(["Nome", "Certificado"])
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: self.tab_part.insertRow(self.tab_part.rowCount()))
        l.addWidget(QLabel("Programa:"))
        l.addWidget(self.txt_treino)
        l.addWidget(self.tab_part)
        l.addWidget(btn_add)
        return w

    def _tab_asbuilt(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.tab_asb = QTableWidget(0, 2)
        self.tab_asb.setHorizontalHeaderLabels(["Doc", "Notas"])
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: self.tab_asb.insertRow(self.tab_asb.rowCount()))
        l.addWidget(self.tab_asb)
        l.addWidget(btn_add)
        return w

    def _tab_anexos(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.txt_anx = QTextEdit()
        l.addWidget(QLabel("Descrição Anexos:"))
        l.addWidget(self.txt_anx)
        return w

    def capturar(self):
        d = {}
        d['identificacao_projeto'] = {"nome_projeto": self.in_nome.text(), "cliente": self.in_cli.text(), "local_instalacao": self.in_loc.text(), "empresa_responsavel": self.in_emp.text(), "data_versao": self.in_dat.text(), "num_contrato": self.in_con.text()}
        d['escopo_premissas'] = {"objetivos": self.txt_obj.toPlainText(), "limites_fornecimento": self.txt_lim.toPlainText(), "premissas": self.txt_prem.toPlainText(), "interfaces": self.txt_int.toPlainText()}
        
        # Tabelas simples
        d['lista_documentos_projeto'] = self._ler_tabela(self.tab_docs, ["titulo", "codigo", "revisao", "data", "autor", "status"])
        d['diagramas_desenhos'] = {"notas": self.txt_diag.toPlainText()}
        d['lista_instrumentos'] = self._ler_tabela(self.tab_inst, ["tag", "descricao", "fabricante_modelo", "faixa", "sinal", "localizacao"])
        d['programacao_logica'] = self._ler_tabela(self.tab_prog, ["ficheiro", "descricao"])
        d['testes_comissionamento'] = {"procedimentos": self.txt_proc.toPlainText(), "relatorios": self.txt_rel.toPlainText(), "nao_conformidades": self.txt_nc.toPlainText()}
        
        op = {"procedimentos_manutencao": self.txt_manut.toPlainText(), "sobressalentes": self.txt_sobr.toPlainText()}
        op["manual_tipo"] = "texto" if self.rad_txt.isChecked() else "pdf"
        op["manual_conteudo"] = self.txt_man.toPlainText() if self.rad_txt.isChecked() else self.in_pdf_man.text()
        d['operacao_manutencao'] = op
        
        d['treinamento'] = {"programa": self.txt_treino.toPlainText(), "participantes": self._ler_tabela(self.tab_part, ["nome", "certificado"])}
        d['documentos_as_built'] = self._ler_tabela(self.tab_asb, ["documento", "notas"])
        d['anexos'] = {"descricao": self.txt_anx.toPlainText()}
        return d

    def _ler_tabela(self, table, keys):
        res = []
        for r in range(table.rowCount()):
            item = {}
            for c, k in enumerate(keys):
                it = table.item(r, c)
                item[k] = it.text() if it else ""
            res.append(item)
        return res

    def ir_anexos(self):
        self.dados_form = self.capturar()
        self.stack.setCurrentWidget(self.widget_anexos)

    def gerar_final(self, files):
        dados_str = json.dumps(self.dados_form)
        uploads = []
        for p in files:
            uploads.append(('anexos', (os.path.basename(p), open(p, 'rb'), 'application/pdf')))
            
        self.thread_ger = QThread()
        self.w_ger = GeracaoDocumentoWorker(self.servico_id, {'dados_formulario': dados_str}, uploads)
        self.w_ger.moveToThread(self.thread_ger)
        self.thread_ger.started.connect(self.w_ger.run)
        self.w_ger.finished.connect(self.pos_geracao)
        self.thread_ger.start()

    def pos_geracao(self, status, data):
        self.thread_ger.quit()
        if status == 201:
            QMessageBox.information(self, "Sucesso", "Documento gerado!")
            self.carregar_historico()
            self.stack.setCurrentWidget(self.widget_form)
        else:
            QMessageBox.critical(self, "Erro", f"Falha: {data.get('erro')}")

    def carregar_historico(self):
        self.lista_hist.clear()
        self.thread_h = QThread()
        self.w_h = ApiWorker("get", f"/api/servicos/{self.servico_id}/documentos")
        self.w_h.moveToThread(self.thread_h)
        self.thread_h.started.connect(self.w_h.run)
        self.w_h.finished.connect(self.pos_historico)
        self.thread_h.start()

    def pos_historico(self, status, data):
        self.thread_h.quit()
        if status == 200:
            for doc in data:
                i = QListWidgetItem(f"{doc['data_criacao']} - v{doc['versao']}")
                i.setData(Qt.UserRole, doc['id'])
                self.lista_hist.addItem(i)

    def ver_detalhes(self, item):
        did = item.data(Qt.UserRole)
        # Implementar carregamento reverso para preencher campos se necessário
        pass

    def excluir_historico(self):
        item = self.lista_hist.currentItem()
        if not item: return
        did = item.data(Qt.UserRole)
        
        if QMessageBox.question(self, "Excluir", "Apagar documento?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.thread_del = QThread()
            self.w_del = ApiWorker("delete", f"/api/documentos/{did}")
            self.w_del.moveToThread(self.thread_del)
            self.thread_del.started.connect(self.w_del.run)
            self.w_del.finished.connect(lambda s, d: self.carregar_historico())
            self.thread_del.start()

class DropArea(QLabel):
    filesDropped = Signal(list)
    def __init__(self):
        super().__init__("\nArraste PDFs aqui")
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 2px dashed #888;")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()

    def dropEvent(self, e):
        urls = [u.toLocalFile() for u in e.mimeData().urls()]
        self.filesDropped.emit([u for u in urls if u.endswith('.pdf')])

class GeracaoDocumentoWorker(QObject):
    finished = Signal(int, dict)
    def __init__(self, sid, data, files):
        super().__init__()
        self.sid, self.data, self.files = sid, data, files
    
    def run(self):
        global access_token
        try:
            r = requests.post(f"{API_BASE_URL}/api/servicos/{self.sid}/documentos", headers={'Authorization': f'Bearer {access_token}'}, data=self.data, files=self.files, timeout=60)
            self.finished.emit(r.status_code, r.json() if r.content else {})
        except Exception as e:
            self.finished.emit(-1, {"erro": str(e)})

class AnexosWidget(QWidget):
    voltar_solicitado = Signal()
    gerar_documento_solicitado = Signal(list)

    def __init__(self):
        super().__init__()
        self.files = []
        l = QVBoxLayout(self)
        
        self.drop = DropArea()
        self.drop.filesDropped.connect(self.add_files)
        self.list = QListWidget()
        
        btns = QHBoxLayout()
        b_voltar = QPushButton("Voltar")
        b_gerar = QPushButton("Gerar Final")
        b_voltar.clicked.connect(self.voltar_solicitado.emit)
        b_gerar.clicked.connect(lambda: self.gerar_documento_solicitado.emit(self.files))
        
        btns.addWidget(b_voltar)
        btns.addWidget(b_gerar)
        
        l.addWidget(self.drop)
        l.addWidget(self.list)
        l.addLayout(btns)

    def add_files(self, fs):
        for f in fs:
            if f not in self.files:
                self.files.append(f)
                self.list.addItem(os.path.basename(f))

# ==============================================================================
# 5. CLASSE DA JANELA PRINCIPAL
# ==============================================================================

class JanelaPrincipal(QMainWindow):
    logoff_requested = Signal()

    def __init__(self):
        super().__init__()
        try:
            self.setWindowTitle("Sistema de Gestão")
            self.resize(1280, 720)
            self.dados_usuario = {}
            
            self.stacked_widget = QStackedWidget()
            
            self.tela_dash = DashboardWidget()
            self.tela_estoque = GestaoEstoqueWidget()
            self.tela_entrada = EntradaRapidaWidget()
            self.tela_saida = SaidaRapidaWidget()
            self.tela_rel = RelatoriosWidget()
            self.tela_forn = FornecedoresWidget()
            self.tela_nat = NaturezasWidget()
            self.tela_user = None
            self.tela_imp = ImportacaoWidget()
            self.tela_term = TerminalWidget()
            self.tela_doc = None
            
            self.stacked_widget.addWidget(self.tela_dash)
            self.stacked_widget.addWidget(self.tela_estoque)
            self.stacked_widget.addWidget(self.tela_entrada)
            self.stacked_widget.addWidget(self.tela_saida)
            self.stacked_widget.addWidget(self.tela_rel)
            self.stacked_widget.addWidget(self.tela_forn)
            self.stacked_widget.addWidget(self.tela_nat)
            self.stacked_widget.addWidget(self.tela_imp)
            self.stacked_widget.addWidget(self.tela_term)
            
            # Menus
            bar = self.menuBar()
            m_arq = bar.addMenu("Arquivo")
            m_arq.addAction("Dashboard", self.mostrar_dash)
            self.act_tema = m_arq.addAction("Mudar Tema", self.trocar_tema)
            m_arq.addAction("Mudar Senha", MudarSenhaDialog(self).exec)
            m_arq.addAction("Logoff", self.logoff_requested.emit)
            m_arq.addAction("Sair", self.close)
            
            m_cad = bar.addMenu("Cadastros")
            m_cad.addAction("Inventário", self.mostrar_estoque)
            m_cad.addAction("Fornecedores", self.mostrar_forn)
            m_cad.addAction("Naturezas", self.mostrar_nat)
            m_cad.addAction("Importar CSV", self.mostrar_imp)
            self.act_users = m_cad.addAction("Usuários", self.mostrar_user)
            
            m_ops = bar.addMenu("Operações")
            m_ops.addAction("Entrada Rápida", self.mostrar_entrada)
            m_ops.addAction("Saída Rápida", self.mostrar_saida)
            m_ops.addAction("Terminal", self.mostrar_term)
            m_ops.addAction("Documentação", self.mostrar_doc)
            
            m_rel = bar.addMenu("Relatórios")
            m_rel.addAction("Gerar", self.mostrar_rel)
            
            m_ajuda = bar.addMenu("Ajuda")
            m_ajuda.addAction("Sobre", SobreDialog(self).exec)
            
            # Layout Principal
            central = QWidget()
            self.setCentralWidget(central)
            layout = QHBoxLayout(central)
            
            # Sidebar
            sidebar = QWidget()
            sidebar.setFixedWidth(220)
            l_side = QVBoxLayout(sidebar)
            l_side.setAlignment(Qt.AlignmentFlag.AlignTop)
            
            btns = [
                ("🏠 Dashboard", self.mostrar_dash),
                ("📦 Inventário", self.mostrar_estoque),
                ("🛰️ Terminal", self.mostrar_term),
                ("➡️ Entrada", self.mostrar_entrada),
                ("⬅️ Saída", self.mostrar_saida),
                ("📄 Relatórios", self.mostrar_rel),
                ("🚚 Fornecedores", self.mostrar_forn),
                ("🌿 Naturezas", self.mostrar_nat)
            ]
            
            for txt, func in btns:
                b = QPushButton(txt)
                b.clicked.connect(func)
                l_side.addWidget(b)
            
            self.btn_users = QPushButton("👥 Usuários")
            self.btn_users.clicked.connect(self.mostrar_user)
            l_side.addWidget(self.btn_users)
            
            b_log = QPushButton("🚪 Logoff")
            b_log.setObjectName("btnLogoff")
            b_log.clicked.connect(self.logoff_requested.emit)
            l_side.addStretch(1)
            l_side.addWidget(b_log)
            
            layout.addWidget(sidebar)
            layout.addWidget(self.stacked_widget)
            
            # Sinais cruzados
            self.tela_dash.ir_para_produtos.connect(self.mostrar_estoque)
            self.tela_dash.ir_para_entrada_rapida.connect(self.mostrar_entrada)
            self.tela_term.ir_para_novo_produto.connect(self.novo_prod_estoque)
            self.tela_entrada.estoque_atualizado.connect(self.tela_estoque.inventario_view.carregar_dados_inventario)
            self.tela_saida.estoque_atualizado.connect(self.tela_estoque.inventario_view.carregar_dados_inventario)
            self.tela_imp.produtos_importados_sucesso.connect(self.tela_estoque.inventario_view.carregar_dados_inventario)
            
            self.statusBar().showMessage("Pronto.")
        except Exception:
            pass

    def carregar_dados_usuario(self, dados):
        self.dados_usuario = dados
        if dados.get('permissao') == 'Administrador':
            if not self.tela_user:
                self.tela_user = UsuariosWidget()
                self.stacked_widget.addWidget(self.tela_user)
        else:
            self.btn_users.hide()
            self.act_users.setVisible(False)

    def novo_prod_estoque(self):
        self.mostrar_estoque()
        self.tela_estoque.inventario_view.abrir_formulario_adicionar()

    def mostrar_dash(self): 
        self.tela_dash.carregar_dados_dashboard(self.dados_usuario.get('nome', ''))
        self.stacked_widget.setCurrentWidget(self.tela_dash)
    def mostrar_estoque(self): self.stacked_widget.setCurrentWidget(self.tela_estoque)
    def mostrar_entrada(self): self.stacked_widget.setCurrentWidget(self.tela_entrada)
    def mostrar_saida(self): self.stacked_widget.setCurrentWidget(self.tela_saida)
    def mostrar_rel(self): self.stacked_widget.setCurrentWidget(self.tela_rel)
    def mostrar_forn(self): self.stacked_widget.setCurrentWidget(self.tela_forn)
    def mostrar_nat(self): self.stacked_widget.setCurrentWidget(self.tela_nat)
    def mostrar_imp(self): self.stacked_widget.setCurrentWidget(self.tela_imp)
    def mostrar_term(self): self.stacked_widget.setCurrentWidget(self.tela_term)
    def mostrar_user(self): 
        if self.tela_user: self.stacked_widget.setCurrentWidget(self.tela_user)
    
    def mostrar_doc(self):
        if not self.tela_doc:
            self.tela_doc = DocumentacaoWidget(1)
            self.stacked_widget.addWidget(self.tela_doc)
        self.stacked_widget.setCurrentWidget(self.tela_doc)

    def trocar_tema(self):
        global CURRENT_THEME
        novo = "dark" if CURRENT_THEME == "light" else "light"
        estilo = load_stylesheet(novo)
        QApplication.instance().setStyleSheet(estilo)
        self.act_tema.setText("Tema Claro" if novo == "dark" else "Tema Escuro")
        QSettings("Empresa", "Estoque").setValue("theme", novo)

class SobreDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sobre")
        l = QVBoxLayout(self)
        
        img = QLabel()
        img.setPixmap(QPixmap(resource_path("logo2.png")).scaled(150, 90, Qt.AspectRatioMode.KeepAspectRatio))
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        txt = QLabel("<b>Sistema de Estoque v2.5</b><br>Desenvolvido em Python/PySide6.")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        btn = QPushButton("OK")
        btn.clicked.connect(self.accept)
        
        l.addWidget(img)
        l.addWidget(txt)
        l.addWidget(btn)

class DashboardWidget(QWidget):
    ir_para_produtos = Signal()
    ir_para_entrada_rapida = Signal()

    def __init__(self):
        super().__init__()
        l = QVBoxLayout(self)
        l.setContentsMargins(30, 20, 30, 20)
        
        topo = QFrame()
        topo.setObjectName("welcomeCard")
        lt = QHBoxLayout(topo)
        self.lbl_nome = QLabel("Bem-vindo!")
        self.lbl_nome.setStyleSheet("font-size: 20px; font-weight: bold;")
        lt.addWidget(self.lbl_nome)
        
        kpis = QHBoxLayout()
        self.kpi_prod = self._mk_kpi("Produtos", "📦")
        self.kpi_forn = self._mk_kpi("Fornecedores", "🚚")
        self.kpi_val = self._mk_kpi("Valor Estoque", "💰")
        kpis.addWidget(self.kpi_prod)
        kpis.addWidget(self.kpi_forn)
        kpis.addWidget(self.kpi_val)
        
        acoes = QHBoxLayout()
        b_ent = QPushButton("Entrada Rápida")
        b_ent.clicked.connect(self.ir_para_entrada_rapida.emit)
        acoes.addWidget(b_ent)
        
        l.addWidget(topo)
        l.addLayout(kpis)
        l.addLayout(acoes)
        l.addStretch(1)
        
        # Clique no KPI leva ao inventário
        self.kpi_prod.mouseReleaseEvent = lambda e: self.ir_para_produtos.emit()

    def _mk_kpi(self, titulo, icone):
        f = QFrame()
        f.setObjectName("kpiCard")
        l = QVBoxLayout(f)
        l.addWidget(QLabel(f"{icone} {titulo}"))
        lbl_val = QLabel("--")
        lbl_val.setObjectName("kpiValue")
        l.addWidget(lbl_val)
        f.lbl_val = lbl_val
        return f

    def carregar_dados_dashboard(self, nome):
        self.lbl_nome.setText(f"Olá, {nome.split()[0]}!")
        global access_token
        try:
            r = requests.get(f"{API_BASE_URL}/api/dashboard/kpis", headers={'Authorization': f'Bearer {access_token}'})
            if r.status_code == 200:
                d = r.json()
                self.kpi_prod.lbl_val.setText(str(d.get('total_produtos', 0)))
                self.kpi_forn.lbl_val.setText(str(d.get('total_fornecedores', 0)))
                self.kpi_val.lbl_val.setText(f"R$ {d.get('valor_total_estoque', 0):.2f}")
        except: pass

# ==============================================================================
# 6. LOGIN E EXECUÇÃO
# ==============================================================================

class JanelaLogin(QMainWindow):
    login_successful = Signal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Login")
        
        w = QWidget()
        self.setCentralWidget(w)
        l = QHBoxLayout(w)
        
        # Painel Esq
        esq = QFrame()
        esq.setStyleSheet("background-color: #2c3e50; color: white;")
        le = QVBoxLayout(esq)
        le.addWidget(QLabel("<h1>Sistema Estoque</h1>"))
        le.addStretch(1)
        
        # Painel Dir
        dir = QFrame()
        ld = QVBoxLayout(dir)
        ld.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.in_user = QLineEdit()
        self.in_user.setPlaceholderText("Usuário")
        self.in_pass = QLineEdit()
        self.in_pass.setPlaceholderText("Senha")
        self.in_pass.setEchoMode(QLineEdit.EchoMode.Password)
        btn = QPushButton("Entrar")
        
        ld.addWidget(QLabel("<h2>Login</h2>"))
        ld.addWidget(self.in_user)
        ld.addWidget(self.in_pass)
        ld.addWidget(btn)
        
        l.addWidget(esq, 1)
        l.addWidget(dir, 1)
        
        btn.clicked.connect(self.logar)
        self.in_pass.returnPressed.connect(self.logar)

    def logar(self):
        u = self.in_user.text()
        p = self.in_pass.text()
        if not u or not p: return
        
        global access_token
        try:
            r = requests.post(f"{API_BASE_URL}/api/login", json={"login": u, "senha": p})
            if r.status_code == 200:
                access_token = r.json()['access_token']
                # Pega dados do usuário
                me = requests.get(f"{API_BASE_URL}/api/usuario/me", headers={'Authorization': f'Bearer {access_token}'})
                self.login_successful.emit(me.json() if me.status_code == 200 else {})
                self.close()
            else:
                QMessageBox.warning(self, "Erro", "Login inválido")
        except:
            show_connection_error_message(self)

class AppManager:
    def __init__(self):
        self.login = None
        self.main = None
    
    def start(self):
        self.login = JanelaLogin()
        self.login.login_successful.connect(self.open_main)
        self.login.showMaximized()
    
    def open_main(self, user_data):
        self.main = JanelaPrincipal()
        self.main.carregar_dados_usuario(user_data)
        self.main.show()
        self.main.mostrar_dash()
        self.main.logoff_requested.connect(self.logout)
        check_for_updates()
    
    def logout(self):
        self.main.close()
        self.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Carregar Tema
    settings = QSettings("Empresa", "Estoque")
    saved = settings.value("theme", "light")
    app.setStyleSheet(load_stylesheet(saved))
    
    mgr = AppManager()
    mgr.start()
    
    sys.exit(app.exec())
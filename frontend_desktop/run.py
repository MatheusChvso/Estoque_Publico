import sys
import os
import threading
import traceback
from waitress import serve
from PySide6.QtWidgets import QApplication, QMessageBox

# --- Configuração de Caminho ---
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend'))
sys.path.insert(0, backend_path)

# --- Imports do Nosso Projeto ---
from app import app
from main_ui import AppManager, resource_path

# --- Função para Rodar o Servidor ---
def run_server():
    """Inicia o servidor Flask usando Waitress em uma porta específica."""
    print("Iniciando servidor Flask em segundo plano...")
    serve(app, host='0.0.0.0', port=5000)

# --- Bloco de Execução Principal ---
if __name__ == "__main__":
    # Bloco de depuração global para apanhar qualquer erro que impeça a aplicação de iniciar
    try:
        # 1. Inicia o servidor em uma thread separada
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # 2. Inicia a aplicação PySide6 (front-end)
        print("Iniciando a interface gráfica...")
        app_qt = QApplication(sys.argv)
        
        try:
            with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
                app_qt.setStyleSheet(f.read())
        except FileNotFoundError:
            print("AVISO: Arquivo de estilo (style.qss) não encontrado.")
        
        # Cria o gestor e inicia a aplicação
        manager = AppManager()
        manager.start()
        
        sys.exit(app_qt.exec())

    except Exception as e:
        # Se qualquer erro acontecer, ele será escrito num ficheiro no Ambiente de Trabalho
        error_log_path = os.path.join(os.path.expanduser("~"), "Desktop", "crash_log.txt")
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"Ocorreu um erro fatal na aplicação:\n\n")
            f.write(f"{e}\n\n")
            f.write(traceback.format_exc())
        
        # Mostra uma mensagem simples a avisar o utilizador
        error_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erro Crítico", f"A aplicação falhou ao iniciar. Verifique o ficheiro 'crash_log.txt' no seu Ambiente de Trabalho para mais detalhes.")
        sys.exit(1)

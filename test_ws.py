# test_ws.py
import websocket
import threading

def on_message(ws, message):
    print(f"--- Message reçu --- \n{message}\n--------------------")

def on_error(ws, error):
    print(f"!!!!!! Erreur !!!!!!! \n{error}\n!!!!!!!!!!!!!!!!!!!!!")

def on_close(ws, close_status_code, close_msg):
    print("### Connexion fermée ###")

def on_open(ws):
    print("### Connexion ouverte avec succès ! En attente de messages... ###")

if __name__ == "__main__":
    # 1. Connectez-vous à votre application et récupérez un token JWT valide.
    # 2. Collez ce token ci-dessous.
    TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJsb2xvIiwiZXhwIjoxNzU3NDcwMTA2fQ.nZcXSRQOAIR12BxSYkV9J-1ifz7Ha-cNW8X1TgqRUwY"

    if "VOTRE TOKEN" in TOKEN:
        print("Veuillez remplacer 'COPIEZ-COLLEZ VOTRE TOKEN JWT VALIDE ICI' par un vrai token.")
    else:
        ws_url = f"ws://localhost:8000/api/v2/ws?token={TOKEN}"
        
        # Active le traçage pour voir la poignée de main en détail
        websocket.enableTrace(True) 
        
        ws = websocket.WebSocketApp(ws_url,
                                  on_open=on_open,
                                  on_message=on_message,
                                  on_error=on_error,
                                  on_close=on_close)
        ws.run_forever()
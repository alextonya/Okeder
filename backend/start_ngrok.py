"""Lance le tunnel ngrok et affiche l'URL publique."""
from pyngrok import ngrok, conf

conf.get_default().auth_token = "3ETysup6tzhY4Z5wkBCFVZJdWM7_234ZngHKNTssWX1CyirBe"
tunnel = ngrok.connect(8000)
public_url = tunnel.public_url.replace("http://", "https://")
print(f"\n{'='*50}")
print(f"  URL publique Okeder : {public_url}")
print(f"  Mini App             : {public_url}/mini-app/TEST")
print(f"{'='*50}\n")
print(f"Copie cette URL : {public_url}")
print("\nCtrl+C pour arrêter le tunnel.")

try:
    ngrok.run()
except KeyboardInterrupt:
    ngrok.kill()

import requests
import yaml


class TelegramNotifier:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.token = self.config['telegram']['bot_token']
        self.subscribers = self.config['telegram']['subscribers']

    def send_alert(self, message):
        """Sends the message to ALL subscribers in config.yaml"""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        print(f"[ALERT] Broadcasting: {message}")

        for chat_id in self.subscribers:
            try:
                payload = {"chat_id": chat_id, "text": message}
                requests.post(url, data=payload)
            except Exception as e:
                print(f"Failed to send to {chat_id}: {e}")
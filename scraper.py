import os
import sys
import requests
from bs4 import BeautifulSoup

# Configuración de Telegram desde variables de entorno de GitHub Secrets
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Configuración de Headers para evitar bloqueos básicos (simula navegador móvil)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

def clean_team_name(name):
    """Normaliza nombres de equipos para facilitar el cruce de datos."""
    if not name:
        return ""
    remove_words = ["fc", "cf", "cd", "ud", "ca", "sv", "sc", "rc", "atlético", "atletico", "real", "de", "the"]
    name = name.lower().strip()
    for word in remove_words:
        name = name.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
    return "".join(e for e in name if e.isalnum())

def scrape_sportsgambler():
    """Extrae pronósticos de SportsGambler."""
    predictions = []
    url = "https://www.sportsgambler.com/football/tips/"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return predictions
        
        soup = BeautifulSoup(response.text, 'lxml')
        # Selector típico de SportsGambler para los bloques de partidos
        containers = soup.select('.feed-item, .game-prediction-card, .tips-post-block')
        
        for item in containers:
            try:
                # Ajustar selectores según la estructura del DOM activa
                teams_element = item.select_one('.teams, .title, h3')
                pick_element = item.select_one('.prediction, .pick, .bet-tip')
                
                if teams_element and pick_element:
                    raw_title = teams_element.text.strip()
                    # Separar equipos comúnmente divididos por 'vs' o 'v'
                    delimiter = " vs " if " vs " in raw_title.lower() else " v "
                    if delimiter in raw_title.lower():
                        home, away = raw_title.lower().split(delimiter, 1)
                    else:
                        continue
                        
                    predictions.append({
                        "home_raw": home.strip(),
                        "away_raw": away.strip(),
                        "home_clean": clean_team_name(home),
                        "away_clean": clean_team_name(away),
                        "pick": pick_element.text.strip(),
                        "source": "SportsGambler"
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"Error scraping SportsGambler: {e}")
    return predictions

def scrape_scoutingstats():
    """Extrae pronósticos de valor de ScoutingStats."""
    predictions = []
    url = "https://scoutingstats.ai/value-bets"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            return predictions
            
        soup = BeautifulSoup(response.text, 'lxml')
        # Selector adaptado para las filas o tarjetas de Value Bets
        rows = soup.select('table tr, .value-bet-row, .prediction-card')
        
        for row in rows:
            try:
                # Intenta extraer de celdas de tabla o elementos flex
                cells = row.select('td, .cell')
                if len(cells) >= 3:
                    match_text = cells[0].text.strip() # Ej: "Real Madrid vs Barcelona"
                    pick_text = cells[1].text.strip()  # Pronóstico o mercado de valor
                    
                    delimiter = " vs " if " vs " in match_text.lower() else " - "
                    if delimiter in match_text.lower():
                        home, away = match_text.lower().split(delimiter, 1)
                        predictions.append({
                            "home_raw": home.strip(),
                            "away_raw": away.strip(),
                            "home_clean": clean_team_name(home),
                            "away_clean": clean_team_name(away),
                            "pick": pick_text,
                            "source": "ScoutingStats"
                        })
            except Exception:
                continue
    except Exception as e:
        print(f"Error scraping ScoutingStats: {e}")
    return predictions

def cross_reference_and_filter(list_a, list_b):
    """Cruza ambas fuentes buscando coincidencia de partidos y lógica de valor."""
    matches_found = []
    
    for item_a in list_a:
        for item_b in list_b:
            # Validar si coinciden los equipos locales y visitantes (limpios)
            same_match = (item_a["home_clean"] == item_b["home_clean"]) or \
                         (item_a["home_clean"] in item_b["home_clean"]) or \
                         (item_b["home_clean"] in item_a["home_clean"])
                         
            if same_match:
                # Aquí se genera la coincidencia de valor sustentado
                # Si ambas fuentes proponen un análisis para el mismo juego, se considera verificado
                matches_found.append({
                    "match": f"{item_a['home_raw'].title()} vs {item_a['away_raw'].title()}",
                    "tip_source_1": item_a["pick"],
                    "tip_source_2": item_b["pick"]
                })
    return matches_found

def send_telegram_alert(alerts):
    """Envía los partidos filtrados y validados a Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Credenciales de Telegram no configuradas en los Secrets.")
        sys.exit(1)
        
    base_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    for alert in alerts:
        message = (
            f"🚨 *APUESTA VALIDADA (Multi-Fuente)* 🚨\n\n"
            f"⚽ *Partido:* {alert['match']}\n"
            f"📊 *SG Tip:* {alert['tip_source_1']}\n"
            f"📈 *SS Value:* {alert['tip_source_2']}\n\n"
            f"💡 _Fundamento: Coincidencia analítica detectada en ambas fuentes de predicción._"
        )
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(base_url, json=payload, timeout=10)
        except Exception as e:
            print(f"Error enviando mensaje: {e}")

def main():
    print("Iniciando scraping de fuentes...")
    sg_tips = scrape_sportsgambler()
    ss_tips = scrape_scoutingstats()
    
    print(f"Detectados {len(sg_tips)} en SportsGambler y {len(ss_tips)} en ScoutingStats.")
    
    validated_bets = cross_reference_and_filter(sg_tips, ss_tips)
    
    if validated_bets:
        print(f"Se encontraron {len(validated_bets)} coincidencias de valor. Enviando alertas...")
        send_telegram_alert(validated_bets)
    else:
        print("No se encontraron coincidencias directas en esta ejecución.")

if __name__ == "__main__":
    main()

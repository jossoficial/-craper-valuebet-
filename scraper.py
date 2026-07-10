import os
import sys
import cloudscraper
from bs4 import BeautifulSoup
import requests

# Configuración de variables de entorno
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Cliente HTTP con evasión avanzada de bloqueos por Cloudflare
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'android',
        'desktop': False
    }
)

def clean_team_name(name):
    """Limpia y estandariza los nombres de los equipos para el cruce de datos."""
    if not name:
        return ""
    name = name.lower().strip()
    
    # Remover tildes comunes
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
        
    # Palabras vacías en el fútbol global
    stop_words = ["fc", "cf", "cd", "ud", "ca", "sv", "sc", "rc", "club", "atletico", "real", "de", "the", "chivas"]
    for word in stop_words:
        name = name.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
        
    return "".join(e for e in name if e.isalnum())

# =====================================================================
# BLOQUE DE EXTRACCIÓN (5 FUENTES)
# =====================================================================

def get_source_1():
    """Fuente 1: SportsGambler"""
    tips = []
    try:
        res = scraper.get("https://www.sportsgambler.com/football/tips/", timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'lxml')
            cards = soup.select('.feed-item, .game-prediction-card, .tips-post-block, article')
            for c in cards:
                title_el = c.select_one('.teams, .title, h3')
                pick_el = c.select_one('.prediction, .pick, .bet-tip, .tip')
                if title_el and pick_el:
                    title = title_el.text.lower()
                    delim = " vs " if " vs " in title else " v "
                    if delim in title:
                        home, away = title.split(delim, 1)
                        tips.append({"home": home.strip(), "away": away.strip(), "pick": pick_el.text.strip(), "source": "SportsGambler"})
    except Exception as e:
        print(f"[!] Error Fuente 1: {e}")
    return tips

def get_source_2():
    """Fuente 2: ScoutingStats"""
    tips = []
    try:
        res = scraper.get("https://scoutingstats.ai/value-bets", timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'lxml')
            rows = soup.select('table tr, .value-bet-row, .prediction-card, div.flex')
            for r in rows:
                cells = r.select('td, .cell, span')
                if len(cells) >= 2:
                    match_text = cells[0].text.lower()
                    delim = " vs " if " vs " in match_text else " - "
                    if delim in match_text:
                        home, away = match_text.split(delim, 1)
                        tips.append({"home": home.strip(), "away": away.strip(), "pick": cells[1].text.strip(), "source": "ScoutingStats"})
    except Exception as e:
        print(f"[!] Error Fuente 2: {e}")
    return tips

def get_source_3():
    """Fuente 3: PredictZ"""
    tips = []
    try:
        res = scraper.get("https://www.predictz.com/football-predictions/today/", timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'lxml')
            rows = soup.select('.ptablerow, tr.ptablehead + tr, [class*="match-row"]')
            for r in rows:
                home_el = r.select_one('.pthome, .team-home')
                away_el = r.select_one('.ptaway, .team-away')
                pred_el = r.select_one('.ptpred, .prediction')
                if home_el and away_el and pred_el:
                    tips.append({"home": home_el.text.strip(), "away": away_el.text.strip(), "pick": pred_el.text.strip(), "source": "PredictZ"})
    except Exception as e:
        print(f"[!] Error Fuente 3: {e}")
    return tips

def get_source_4():
    """Fuente 4: Forebet"""
    tips = []
    try:
        res = scraper.get("https://www.forebet.com/en/football-tips-and-predictions-for-today", timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'lxml')
            rows = soup.select('.schema-row, .mainpx12')
            for r in rows:
                home_el = r.select_one('.homeTeam, span[itemprop="homeTeam"]')
                away_el = r.select_one('.awayTeam, span[itemprop="awayTeam"]')
                pred_el = r.select_one('.fprc, .predict-cell')
                if home_el and away_el and pred_el:
                    tips.append({"home": home_el.text.strip(), "away": away_el.text.strip(), "pick": pred_el.text.strip(), "source": "Forebet"})
    except Exception as e:
        print(f"[!] Error Fuente 4: {e}")
    return tips

def get_source_5():
    """Fuente 5: Vitibet"""
    tips = []
    try:
        res = scraper.get("https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en", timeout=15)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'lxml')
            rows = soup.select('table tr')
            for r in rows:
                cells = r.select('td')
                if len(cells) >= 4:
                    home_text = cells[1].text.strip()
                    away_text = cells[2].text.strip()
                    pred_text = cells[3].text.strip() # Tip sugerido (1, X, 2 o Under/Over)
                    if home_text and away_text and len(pred_text) <= 5:
                        tips.append({"home": home_text, "away": away_text, "pick": pred_text, "source": "Vitibet"})
    except Exception as e:
        print(f"[!] Error Fuente 5: {e}")
    return tips

# =====================================================================
# CORE ENGINE: PROCESAMIENTO Y CRUCE
# =====================================================================

def process_and_analyze():
    all_tips = []
    all_tips.extend(get_source_1())
    all_tips.extend(get_source_2())
    all_tips.extend(get_source_3())
    all_tips.extend(get_source_4())
    all_tips.extend(get_source_5())
    
    print(f"[*] Total global de pronósticos recolectados: {len(all_tips)}")
    
    # Agrupar por clave de partido única indexada
    match_groups = {}
    
    for item in all_tips:
        h_clean = clean_team_name(item["home"])
        a_clean = clean_team_name(item["away"])
        
        if not h_clean or not a_clean:
            continue
            
        # Generar un identificador único sin importar el orden local/visitante
        match_key = "_".join(sorted([h_clean, a_clean]))
        
        if match_key not in match_groups:
            match_groups[match_key] = {
                "display_name": f"{item['home'].title()} vs {item['away'].title()}",
                "predictions": []
            }
            
        match_groups[match_key]["predictions"].append({
            "source": item["source"],
            "pick": item["pick"]
        })
        
    # Filtrar solo partidos analizados por 2 o más fuentes independientes
    validated_alerts = []
    for key, data in match_groups.items():
        if len(data["predictions"]) >= 2:
            validated_alerts.append(data)
            
    return validated_alerts

def send_telegram_broadcast(alerts):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Error: Tokens de Telegram ausentes en Secrets.")
        sys.exit(1)
        
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    for alert in alerts:
        # Construir bloque analítico estructurado
        tips_details = ""
        for p in alert["predictions"]:
            tips_details += f"▪️ *{p['source']}:* `{p['pick']}`\n"
            
        message = (
            f"🤖 *SISTEMA IA: APUESTA DETECTADA* 🤖\n\n"
            f"⚽ *Partido:* {alert['display_name']}\n"
            f"📊 *Fuentes Coincidentes:* {len(alert['predictions'])}\n\n"
            f"*Análisis Cruzado:*\n{tips_details}\n"
            f"💡 _Fundamento: Evento identificado y respaldado por múltiples plataformas predictivas._"
        )
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"[!] Fallo al despachar a Telegram: {e}")

def main():
    print("=== INICIANDO SISTEMA MULTI-SCRAPER DE CUOTAS ===")
    results = process_and_analyze()
    print(f"[*] Partidos que superaron el filtro de coincidencia: {len(results)}")
    
    if results:
        send_telegram_broadcast(results)
        print("[+] Alertas enviadas con éxito.")
    else:
        print("[-] No se encontraron cruces lógicos suficientes en esta corrida.")

if __name__ == "__main__":
    main()

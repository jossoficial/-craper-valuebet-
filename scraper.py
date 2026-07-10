import os
import sys
import requests
from bs4 import BeautifulSoup

# Configuración de credenciales protegidas
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")

def clean_team_name(name):
    """Estandariza los nombres de los equipos para el motor de cruce de datos."""
    if not name:
        return ""
    name = name.lower().strip()
    
    # Normalización de caracteres
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
        
    # Limpieza de términos redundantes en fútbol
    stop_words = ["fc", "cf", "cd", "ud", "ca", "sv", "sc", "rc", "club", "atletico", "real", "de", "the", "chivas", "deportivo"]
    for word in stop_words:
        name = name.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
        
    return "".join(e for e in name if e.isalnum())

def fetch_html_via_proxy(target_url):
    """Enruta la petición a través de ScraperAPI encargándose de proxies y JS."""
    if not SCRAPER_API_KEY:
        print("[!] Error: Falta la variable SCRAPER_API_KEY en los Secrets.")
        return None
        
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true'  # Ejecuta JavaScript del lado del servidor proxy
    }
    
    try:
        print(f"-> Solicitando vía ScraperAPI: {target_url}")
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=45)
        print(f"   [Status de la API: {response.status_code}]")
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"   [Error de Conexión Proxy]: {e}")
    return None

# =====================================================================
# EXTRACTORES DE CONTENIDO (PARSERS)
# =====================================================================

def parse_sportsgambler(html):
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    cards = soup.select('.feed-item, .game-prediction-card, .tips-post-block, article, a[href*="/predictions/"]')
    for c in cards:
        title_el = c.select_one('.teams, .title, h3, h4')
        pick_el = c.select_one('.prediction, .pick, .bet-tip, .tip, .prediction-box')
        if title_el and pick_el:
            title = title_el.text.lower()
            delim = " vs " if " vs " in title else " v "
            if delim in title:
                home, away = title.split(delim, 1)
                tips.append({"home": home.strip(), "away": away.strip(), "pick": pick_el.text.strip(), "source": "SportsGambler"})
    return tips

def parse_scoutingstats(html):
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    rows = soup.select('table tr, .value-bet-row, .prediction-card, div.flex, .bet-row')
    for r in rows:
        cells = r.select('td, .cell, span, div')
        if len(cells) >= 2:
            match_text = cells[0].text.lower()
            delim = " vs " if " vs " in match_text else " - "
            if delim in match_text:
                home, away = match_text.split(delim, 1)
                tips.append({"home": home.strip(), "away": away.strip(), "pick": cells[1].text.strip(), "source": "ScoutingStats"})
    return tips

def parse_predictz(html):
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    rows = soup.select('.ptablerow, tr, [class*="match-row"], .match-container')
    for r in rows:
        home_el = r.select_one('.pthome, .team-home, .home')
        away_el = r.select_one('.ptaway, .team-away, .away')
        pred_el = r.select_one('.ptpred, .prediction, .tip')
        if home_el and away_el and pred_el:
            tips.append({"home": home_el.text.strip(), "away": away_el.text.strip(), "pick": pred_el.text.strip(), "source": "PredictZ"})
    return tips

def parse_forebet(html):
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    rows = soup.select('.schema-row, .mainpx12, .tr_0, .tr_1')
    for r in rows:
        home_el = r.select_one('.homeTeam, span[itemprop="homeTeam"], .home-team')
        away_el = r.select_one('.awayTeam, span[itemprop="awayTeam"], .away-team')
        pred_el = r.select_one('.fprc, .predict-cell, .forebet-pred')
        if home_el and away_el and pred_el:
            tips.append({"home": home_el.text.strip(), "away": away_el.text.strip(), "pick": pred_el.text.strip(), "source": "Forebet"})
    return tips

def parse_vitibet(html):
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    rows = soup.select('table tr, .tips-row')
    for r in rows:
        cells = r.select('td')
        if len(cells) >= 4:
            home_text = cells[1].text.strip()
            away_text = cells[2].text.strip()
            pred_text = cells[3].text.strip()
            if home_text and away_text and len(pred_text) <= 8:
                tips.append({"home": home_text, "away": away_text, "pick": pred_text, "source": "Vitibet"})
    return tips

# =====================================================================
# MOTOR CENTRAL DE PROCESAMIENTO
# =====================================================================

def main():
    print("=== INICIANDO CONTROLADOR DE EVENTOS (POWERED BY SCRAPERAPI) ===")
    
    all_tips = []
    
    # Ejecución secuencial de extracción de las 5 fuentes
    html_f1 = fetch_html_via_proxy("https://www.sportsgambler.com/football/tips/")
    f1 = parse_sportsgambler(html_f1)
    print(f"   [+] SportsGambler procesado. Registros: {len(f1)}")
    all_tips.extend(f1)
    
    html_f2 = fetch_html_via_proxy("https://scoutingstats.ai/value-bets")
    f2 = parse_scoutingstats(html_f2)
    print(f"   [+] ScoutingStats procesado. Registros: {len(f2)}")
    all_tips.extend(f2)
    
    html_f3 = fetch_html_via_proxy("https://www.predictz.com/football-predictions/today/")
    f3 = parse_predictz(html_f3)
    print(f"   [+] PredictZ procesado. Registros: {len(f3)}")
    all_tips.extend(f3)
    
    html_f4 = fetch_html_via_proxy("https://www.forebet.com/en/football-tips-and-predictions-for-today")
    f4 = parse_forebet(html_f4)
    print(f"   [+] Forebet procesado. Registros: {len(f4)}")
    all_tips.extend(f4)
    
    html_f5 = fetch_html_via_proxy("https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en")
    f5 = parse_vitibet(html_f5)
    print(f"   [+] Vitibet procesado. Registros: {len(f5)}")
    all_tips.extend(f5)

    print(f"\n[*] Mapeo consolidado completo. Total analizado: {len(all_tips)}")
    
    # Agrupación multidimensional por emparejamiento de equipos
    match_groups = {}
    for item in all_tips:
        h_clean = clean_team_name(item["home"])
        a_clean = clean_team_name(item["away"])
        
        if not h_clean or not a_clean:
            continue
            
        # Generamos una firma única ordenada alfabéticamente
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
        
    # Filtrado estricto: requerimos cruce de al menos 2 plataformas distintas
    validated_alerts = [data for key, data in match_groups.items() if len(data["predictions"]) >= 2]
    print(f"[*] Coincidencias de valor validadas en esta corrida: {len(validated_alerts)}")
    
    # Despacho automatizado a Telegram
    if validated_alerts and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for alert in validated_alerts:
            tips_details = "".join([f"▪️ *{p['source']}:* `{p['pick']}`\n" for p in alert["predictions"]])
            message = (
                f"🤖 *SISTEMA IA: APUESTA CONFIRMADA* 🤖\n\n"
                f"⚽ *Partido:* {alert['display_name']}\n"
                f"📊 *Fuentes Coincidentes:* {len(alert['predictions'])}\n\n"
                f"*Pronósticos Cruzados:*\n{tips_details}\n"
                f"💡 _Fundamento: Señal de valor detectada en múltiples proveedores analíticos._"
            )
            try:
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
            except Exception as e:
                print(f"[!] Error al enviar alerta: {e}")
        print("[+] Todas las alertas válidas fueron enviadas a Telegram.")
    else:
        print("[-] Operación terminada sin alertas despachadas.")

if __name__ == "__main__":
    main()

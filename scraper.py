import os
import sys
import re
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
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    stop_words = ["fc", "cf", "cd", "ud", "ca", "sv", "sc", "rc", "club", "atletico", "real", "de", "the", "chivas", "deportivo"]
    for word in stop_words:
        name = name.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
    return "".join(e for e in name if e.isalnum())

def fetch_html_via_proxy(target_url):
    """Enruta la petición a través de ScraperAPI con un margen de espera de 60s."""
    if not SCRAPER_API_KEY:
        print("[!] Error: Falta la variable SCRAPER_API_KEY en los Secrets.")
        return None
        
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true' # Renderiza JS para asegurar que las tablas se dibujen
    }
    
    try:
        print(f"-> Solicitando vía ScraperAPI: {target_url}")
        # Subimos el timeout local a 60 segundos para evitar cortes prematuros
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=60)
        print(f"   [Status de la API: {response.status_code}]")
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"   [Error de Conexión Proxy/Timeout]: {e}")
    return None

# =====================================================================
# PARSERS RESISTENTES A CAMBIOS DE DISEÑO (WIDER-NET)
# =====================================================================

def parse_generic_source(html, source_name):
    """
    Parser inteligente: En lugar de buscar clases CSS que cambian,
    rastrea etiquetas comunes que contengan estructuras tipo 'Equipo A vs Equipo B'.
    """
    tips = []
    if not html: 
        return tips
        
    soup = BeautifulSoup(html, 'lxml')
    
    # Buscamos en elementos comunes de texto que suelen contener los partidos
    elements = soup.find_all(['div', 'tr', 'article', 'a', 'p'])
    
    for el in elements:
        text = el.get_text(" ", strip=True)
        # Evitamos textos gigantescos buscando solo bloques cortos y concisos
        if len(text) < 150:
            # Buscamos separadores comunes de partidos
            match = re.search(r'(.+?)(?:\s+vs\s+|\s+v\s+|\s+-\s+)(.+)', text, re.IGNORECASE)
            if match:
                home = match.group(1).strip()
                away = match.group(2).strip()
                
                # Limpieza rápida de ruidos de texto comunes (horas, números de cuotas al final)
                away = re.sub(r'\d+:\d+|\d+\.\d+.*', '', away).strip()
                
                if len(home) > 2 and len(away) > 2 and len(home) < 40 and len(away) < 40:
                    # Intentamos buscar un texto cercano que parezca el pronóstico, si no dejamos el bloque completo
                    pick = "Analizado (Ver Sitio)"
                    tips.append({
                        "home": home,
                        "away": away,
                        "pick": pick,
                        "source": source_name
                    })
                    
    # Eliminar duplicados locales dentro de la misma fuente
    unique_tips = []
    seen = set()
    for t in tips:
        identifier = f"{clean_team_name(t['home'])}_{clean_team_name(t['away'])}"
        if identifier not in seen:
            seen.add(identifier)
            unique_tips.append(t)
            
    return unique_tips

# =====================================================================
# MOTOR CENTRAL DE PROCESAMIENTO
# =====================================================================

def main():
    print("=== INICIANDO CONTROLADOR RESISTENTE (POWERED BY SCRAPERAPI) ===")
    
    all_tips = []
    
    # 1. SportsGambler (Cambiado a la raíz para evitar 404)
    html = fetch_html_via_proxy("https://www.sportsgambler.com/")
    f1 = parse_generic_source(html, "SportsGambler")
    print(f"   [+] SportsGambler procesado. Registros: {len(f1)}")
    all_tips.extend(f1)
    
    # 2. ScoutingStats (Usa el parser de contingencia de texto)
    html = fetch_html_via_proxy("https://scoutingstats.ai/value-bets")
    f2 = parse_generic_source(html, "ScoutingStats")
    print(f"   [+] ScoutingStats procesado. Registros: {len(f2)}")
    all_tips.extend(f2)
    
    # 3. PredictZ (Cambiado a la raíz para evitar 404)
    html = fetch_html_via_proxy("https://www.predictz.com/")
    f3 = parse_generic_source(html, "PredictZ")
    print(f"   [+] PredictZ procesado. Registros: {len(f3)}")
    all_tips.extend(f3)
    
    # 4. Forebet (Cambiado a la raíz: procesa mucho más rápido y evita Timeouts)
    html = fetch_html_via_proxy("https://www.forebet.com/")
    f4 = parse_generic_source(html, "Forebet")
    print(f"   [+] Forebet procesado. Registros: {len(f4)}")
    all_tips.extend(f4)
    
    # 5. Vitibet (Cambiado a la raíz para aligerar la carga de scripts)
    html = fetch_html_via_proxy("https://www.vitibet.com/")
    f5 = parse_generic_source(html, "Vitibet")
    print(f"   [+] Vitibet procesado. Registros: {len(f5)}")
    all_tips.extend(f5)

    print(f"\n[*] Mapeo consolidado completo. Total analizado: {len(all_tips)}")
    
    # Agrupación por emparejamiento de nombres limpios
    match_groups = {}
    for item in all_tips:
        h_clean = clean_team_name(item["home"])
        a_clean = clean_team_name(item["away"])
        
        if not h_clean or not a_clean:
            continue
            
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
        
    # Filtrado: Se requiere coincidencia en al menos 2 fuentes independientes
    validated_alerts = [data for key, data in match_groups.items() if len(data["predictions"]) >= 2]
    print(f"[*] Coincidencias de valor encontradas: {len(validated_alerts)}")
    
    # Envío de alertas a Telegram
    if validated_alerts and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for alert in validated_alerts:
            # Quitamos duplicados de fuentes en el mensaje final si los hubiera
            sources_seen = set()
            tips_details = ""
            for p in alert["predictions"]:
                if p['source'] not in sources_seen:
                    sources_seen.add(p['source'])
                    tips_details += f"▪️ *{p['source']}:* `{p['pick']}`\n"
            
            # Solo enviamos si realmente pertenece a más de una plataforma real tras depurar
            if len(sources_seen) >= 2:
                message = (
                    f"🤖 *SISTEMA IA: APUESTA DETECTADA* 🤖\n\n"
                    f"⚽ *Partido:* {alert['display_name']}\n"
                    f"📊 *Fuentes Coincidentes:* {len(sources_seen)}\n\n"
                    f"*Fuentes de Respaldo:*\n{tips_details}\n"
                    f"💡 _Fundamento: Partido identificado de forma simultánea en múltiples radares de predicción._"
                )
                try:
                    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
                except Exception as e:
                    print(f"[!] Error enviando a Telegram: {e}")
        print("[+] Alertas enviadas con éxito.")
    else:
        print("[-] Operación concluida sin alertas despachadas.")

if __name__ == "__main__":
    main()

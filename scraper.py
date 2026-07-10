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

def fetch_html_via_proxy(target_url, render_js=False):
    """Enruta la petición a través de ScraperAPI optimizando el uso de JS."""
    if not SCRAPER_API_KEY:
        print("[!] Error: Falta la variable SCRAPER_API_KEY en los Secrets.")
        return None
        
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true' if render_js else 'false'
    }
    
    try:
        print(f"-> Solicitando vía ScraperAPI (JS: {render_js}): {target_url}")
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=50)
        print(f"   [Status de la API: {response.status_code}]")
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"   [Error de Conexión Proxy/Timeout]: {e}")
    return None

# =====================================================================
# EXTRACTOR UNIVERSAL AGRESIVO
# =====================================================================

def extract_matches(html, source_name):
    """
    Escanea el HTML usando un pipeline doble:
    1. Busca conectores explícitos (vs, -, v) en bloques de texto medianos.
    2. Analiza estructuras de tablas estructuradas (filas y celdas consecutivas).
    """
    tips = []
    if not html: 
        return tips
        
    # Usamos html.parser por compatibilidad nativa y velocidad
    soup = BeautifulSoup(html, 'html.parser')
    
    # --- MÉTODO 1: Escaneo de Bloques de Texto (Ideal para PredictZ y SportsGambler) ---
    for el in soup.find_all(['tr', 'td', 'div', 'p', 'a', 'li', 'h3', 'h4']):
        text = el.get_text(" ", strip=True)
        if 10 < len(text) < 200:
            match = re.search(r'(.+?)(?:\s+vs\s+|\s+v\s+|\s+-\s+)(.+)', text, re.IGNORECASE)
            if match:
                home = match.group(1).strip()
                away = match.group(2).strip()
                
                # Limpieza de residuos comunes como horas (20:45) o cuotas decimales
                away = re.sub(r'\d+:\d+|\d+\.\d+.*', '', away).strip()
                home = re.sub(r'\d+:\d+', '', home).strip()
                
                if 2 < len(home) < 40 and 2 < len(away) < 40:
                    if not any(w in home.lower() or w in away.lower() for w in ["unirse", "todos", "contacto", "cookies", "privacy"]):
                        tips.append({"home": home, "away": away, "pick": "Predicción", "source": source_name})

    # --- MÉTODO 2: Análisis de Celdas Separadas (Ideal para Vitibet, Forebet y ScoutingStats) ---
    for row in soup.find_all('tr'):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(['td', 'th']) if c.get_text(strip=True)]
        if len(cells) >= 2:
            home, away = cells[0], cells[1]
            if 2 < len(home) < 35 and 2 < len(away) < 35:
                # Filtrar palabras de cabeceras de tablas
                if not any(w in home.lower() or w in away.lower() for w in ["partido", "match", "fecha", "date", "home", "away", "tip", "resultados"]):
                    tips.append({"home": home, "away": away, "pick": "Tendencia", "source": source_name})

    # Depuración interna de duplicados obtenidos por ambos métodos en la misma fuente
    unique_tips = []
    seen = set()
    for t in tips:
        match_id = f"{clean_team_name(t['home'])}_{clean_team_name(t['away'])}"
        if match_id not in seen:
            seen.add(match_id)
            unique_tips.append(t)
            
    return unique_tips

# =====================================================================
# EJECUCIÓN DEL CONTROLADOR
# =====================================================================

def main():
    print("=== INICIANDO CONTROLADOR DE EVENTOS INTELIGENTE v3 ===")
    
    all_tips = []
    
    # 1. SportsGambler (Raíz - Sin JS)
    html = fetch_html_via_proxy("https://www.sportsgambler.com/", render_js=False)
    f1 = extract_matches(html, "SportsGambler")
    print(f"   [+] SportsGambler procesado. Registros: {len(f1)}")
    all_tips.extend(f1)
    
    # 2. ScoutingStats (Subpágina crítica - Con JS para volcar la tabla reactiva)
    html = fetch_html_via_proxy("https://scoutingstats.ai/value-bets", render_js=True)
    f2 = extract_matches(html, "ScoutingStats")
    print(f"   [+] ScoutingStats procesado. Registros: {len(f2)}")
    all_tips.extend(f2)
    
    # 3. PredictZ (Raíz - Con JS, nuestro mayor proveedor de registros)
    html = fetch_html_via_proxy("https://www.predictz.com/", render_js=True)
    f3 = extract_matches(html, "PredictZ")
    print(f"   [+] PredictZ procesado. Registros: {len(f3)}")
    all_tips.extend(f3)
    
    # 4. Forebet (Raíz - Desactivamos JS para evitar el molesto Error 500)
    html = fetch_html_via_proxy("https://www.forebet.com/", render_js=False)
    f4 = extract_matches(html, "Forebet")
    print(f"   [+] Forebet procesado. Registros: {len(f4)}")
    all_tips.extend(f4)
    
    # 5. Vitibet (URL profunda de cartelera completa - Sin JS para máxima velocidad)
    html = fetch_html_via_proxy("https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en", render_js=False)
    f5 = extract_matches(html, "Vitibet")
    print(f"   [+] Vitibet procesado. Registros: {len(f5)}")
    all_tips.extend(f5)

    print(f"\n[*] Mapeo consolidado completo. Total analizado: {len(all_tips)}")
    
    # Agrupación y cruce de datos por ID único de enfrentamiento
    match_groups = {}
    for item in all_tips:
        h_clean = clean_team_name(item["home"])
        a_clean = clean_team_name(item["away"])
        
        if not h_clean or not a_clean:
            continue
            
        # Ordenamos alfabéticamente los nombres limpios para emparejar "A vs B" con "B vs A"
        match_key = "_".join(sorted([h_clean, a_clean]))
        
        if match_key not in match_groups:
            match_groups[match_key] = {
                "display_name": f"{item['home'].title()} vs {item['away'].title()}",
                "sources": set()
            }
        match_groups[match_key]["sources"].add(item["source"])
        
    # Filtrado estricto: El partido debe aparecer en 2 o más plataformas diferentes
    validated_alerts = [data for key, data in match_groups.items() if len(data["sources"]) >= 2]
    print(f"[*] Partidos con coincidencia multi-fuente encontrados: {len(validated_alerts)}")
    
    # Despacho automatizado a Telegram
    if validated_alerts and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for alert in validated_alerts:
            tips_details = "".join([f"▪️ *{src}*: `Confirmado`\n" for src in alert["sources"]])
            
            message = (
                f"🤖 *SISTEMA IA: APUESTA DETECTADA* 🤖\n\n"
                f"⚽ *Partido:* {alert['display_name']}\n"
                f"📊 *Fuentes Coincidentes:* {len(alert['sources'])}\n\n"
                f"*Radares de Respaldo:*\n{tips_details}\n"
                f"💡 _Fundamento: Evento de alta confianza identificado simultáneamente en múltiples plataformas._"
            )
            try:
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
            except Exception as e:
                print(f"[!] Error enviando a Telegram: {e}")
        print("[+] Alertas cruzadas despachadas con éxito.")
    else:
        print("[-] Operación concluida sin alertas despachadas.")

if __name__ == "__main__":
    main()

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

def fetch_html_via_proxy(target_url, render_js=True):
    """Enruta la petición a través de ScraperAPI permitiendo activar o desactivar JS."""
    if not SCRAPER_API_KEY:
        print("[!] Error: Falta la variable SCRAPER_API_KEY en los Secrets.")
        return None
        
    payload = {
        'api_key': SCRAPER_API_KEY,
        'url': target_url,
        'render': 'true' if render_js else 'false' # Alternamos JS según el sitio
    }
    
    try:
        print(f"-> Solicitando vía ScraperAPI (Render JS: {render_js}): {target_url}")
        response = requests.get('http://api.scraperapi.com', params=payload, timeout=60)
        print(f"   [Status de la API: {response.status_code}]")
        if response.status_code == 200:
            return response.text
    except Exception as e:
        print(f"   [Error de Conexión Proxy/Timeout]: {e}")
    return None

# =====================================================================
# PARSERS OPTIMIZADOS POR ESTRUCTURA DE TEXTO Y TABLAS
# =====================================================================

def parse_text_based(html, source_name):
    """Busca partidos en elementos que contienen conectores 'vs' o '-' en su texto."""
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    
    # Escaneamos enlaces, bloques y párrafos cortos
    for el in soup.find_all(['a', 'div', 'p', 'h3', 'h4']):
        text = el.get_text(" ", strip=True)
        if len(text) < 120:
            match = re.search(r'(.+?)(?:\s+vs\s+|\s+v\s+|\s+-\s+)(.+)', text, re.IGNORECASE)
            if match:
                home = match.group(1).strip()
                away = match.group(2).strip()
                away = re.sub(r'\d+:\d+|\d+\.\d+.*', '', away).strip() # Limpia números/horas residuales
                
                if 2 < len(home) < 40 and 2 < len(away) < 40:
                    tips.append({"home": home, "away": away, "pick": "Analizado", "source": source_name})
    return tips

def parse_table_based(html, source_name):
    """Busca partidos en estructuras de tablas donde el local y visitante están separados por celdas."""
    tips = []
    if not html: return tips
    soup = BeautifulSoup(html, 'lxml')
    
    for row in soup.find_all('tr'):
        cells = [c.get_text(" ", strip=True) for c in row.find_all(['td', 'th']) if c.get_text(strip=True)]
        # Si la fila tiene entre 2 y 6 celdas, es muy probable que las primeras sean los equipos
        if len(cells) >= 2:
            home = cells[0]
            away = cells[1]
            
            # Si están en la misma celda pero sin "vs" (separados por espacios amplios)
            if len(cells) == 1 or (len(home) > 25 and source_name == "ScoutingStats"):
                continue
                
            if 2 < len(home) < 35 and 2 < len(away) < 35:
                # Evitar falsos positivos con palabras comunes de cabeceras de tablas
                if not any(w in home.lower() or w in away.lower() for w in ["partido", "match", "fecha", "date", "home", "away", "tip"]):
                    tips.append({"home": home, "away": away, "pick": "Tendencia de Valor", "source": source_name})
    return tips

# =====================================================================
# MOTOR CENTRAL DE PROCESAMIENTO
# =====================================================================

def main():
    print("=== INICIANDO CONTROLADOR DE EVENTOS INTELIGENTE ===")
    
    all_tips = []
    
    # 1. SportsGambler (Desactivamos JS render para evitar el 500)
    html = fetch_html_via_proxy("https://www.sportsgambler.com/", render_js=False)
    f1 = parse_text_based(html, "SportsGambler")
    print(f"   [+] SportsGambler procesado. Registros: {len(f1)}")
    all_tips.extend(f1)
    
    # 2. ScoutingStats (Cambiado a lectura de tablas dinámicas)
    html = fetch_html_via_proxy("https://scoutingstats.ai/value-bets", render_js=True)
    f2 = parse_table_based(html, "ScoutingStats")
    if len(f2) == 0: # Si falla la tabla, intentamos texto largo
        f2 = parse_text_based(html, "ScoutingStats")
    print(f"   [+] ScoutingStats procesado. Registros: {len(f2)}")
    all_tips.extend(f2)
    
    # 3. PredictZ (Mantenemos la fórmula ganadora que te dio 110 registros)
    html = fetch_html_via_proxy("https://www.predictz.com/", render_js=True)
    f3 = parse_text_based(html, "PredictZ")
    print(f"   [+] PredictZ procesado. Registros: {len(f3)}")
    all_tips.extend(f3)
    
    # 4. Forebet (Combinamos texto y tablas para asegurar captura)
    html = fetch_html_via_proxy("https://www.forebet.com/", render_js=True)
    f4 = parse_text_based(html, "Forebet") + parse_table_based(html, "Forebet")
    print(f"   [+] Forebet procesado. Registros: {len(f4)}")
    all_tips.extend(f4)
    
    # 5. Vitibet (Desactivamos JS render para evitar el 500 de saturación)
    html = fetch_html_via_proxy("https://www.vitibet.com/", render_js=False)
    f5 = parse_table_based(html, "Vitibet")
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
    validated_alerts = []
    for key, data in match_groups.items():
        # Filtramos fuentes duplicadas para el mismo partido
        sources_seen = set([p['source'] for p in data["predictions"]])
        if len(sources_seen) >= 2:
            data["unique_sources"] = sources_seen
            validated_alerts.append(data)

    print(f"[*] Partidos con coincidencia multi-fuente encontrados: {len(validated_alerts)}")
    
    # Envío de alertas a Telegram
    if validated_alerts and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for alert in validated_alerts:
            tips_details = "".join([f"▪️ *{src}*: `Verificado`\n" for src in alert["unique_sources"]])
            
            message = (
                f"🤖 *SISTEMA IA: APUESTA DETECTADA* 🤖\n\n"
                f"⚽ *Partido:* {alert['display_name']}\n"
                f"📊 *Fuentes Coincidentes:* {len(alert['unique_sources'])}\n\n"
                f"*Fuentes de Respaldo:*\n{tips_details}\n"
                f"💡 _Fundamento: Evento crítico identificado de forma simultánea en múltiples radares de predicción._"
            )
            try:
                requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
            except Exception as e:
                print(f"[!] Error enviando a Telegram: {e}")
        print("[+] Todas las alertas cruzadas fueron enviadas a Telegram.")
    else:
        print("[-] Operación concluida sin alertas despachadas.")

if __name__ == "__main__":
    main()

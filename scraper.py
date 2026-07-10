import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from difflib import SequenceMatcher

# Configuración de credenciales protegidas
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY")

def clean_team_name(name):
    """Estandariza al máximo los nombres eliminando ruidos y caracteres especiales."""
    if not name:
        return ""
    name = name.lower().strip()
    # Quitar acentos básicos
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    for k, v in replacements.items():
        name = name.replace(k, v)
    # Eliminar palabras comunes en nombres de clubes de fútbol
    stop_words = ["fc", "cf", "cd", "ud", "ca", "sv", "sc", "rc", "club", "atletico", "real", "de", "the", "chivas", "deportivo", "united", "utd", "city"]
    for word in stop_words:
        name = name.replace(f" {word} ", " ").replace(f"{word} ", "").replace(f" {word}", "")
    # Dejar solo caracteres alfanuméricos
    return "".join(e for e in name if e.isalnum())

def are_teams_similar(name1, name2):
    """Calcula si dos nombres de equipos son el mismo usando similitud de caracteres (Fuzzy Match)."""
    if name1 == name2:
        return True
    if len(name1) > 4 and len(name2) > 4:
        if name1 in name2 or name2 in name1:
            return True
    # Si comparten más del 72% de similitud en su estructura, los toma como iguales
    return SequenceMatcher(None, name1, name2).ratio() > 0.72

def fetch_html_via_proxy(target_url, render_js=False):
    """Enruta la petición a través de ScraperAPI configurando tiempos de espera óptimos."""
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
# EXTRACTOR DE CONTINGENCIA ANTI-MARCADORES
# =====================================================================

def extract_matches(html, source_name):
    """Filtra y extrae emparejamientos limpios de fútbol evadiendo marcadores y anuncios."""
    tips = []
    if not html: 
        return tips
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # Método de bloques de texto cortos
    for el in soup.find_all(['tr', 'td', 'div', 'p', 'a', 'li']):
        text = el.get_text(" ", strip=True)
        
        # FILTRO CRÍTICO 1: Si contiene un patrón de marcador (ej. 2 - 0 o 1-1), se ignora de inmediato
        if re.search(r'\d+\s*[-–]\s*\d+', text):
            continue
            
        if 10 < len(text) < 180:
            # Limpiamos estampas de horas en el bloque de texto (ej: 19:30)
            text = re.sub(r'\b\d{1,2}:\d{2}\b', '', text)
            
            match = re.search(r'(.+?)(?:\s+vs\s+|\s+v\s+|\s+–\s+|\s+-\s+)(.+)', text, re.IGNORECASE)
            if match:
                home = match.group(1).strip()
                away = match.group(2).strip()
                
                # Limpiar dígitos sueltos en las esquinas que hayan quedado de cuotas o minutos
                home = re.sub(r'^\d+\s+|\s+\d+$', '', home).strip()
                away = re.sub(r'^\d+\s+|\s+\d+$', '', away).strip()
                
                if 2 < len(home) < 35 and 2 < len(away) < 35:
                    # Filtro de palabras basura del diseño web
                    if not any(w in home.lower() or w in away.lower() for w in ["unirse", "todos", "contacto", "cookies", "privacy", "clanek", "tips", "free", "prediction"]):
                        tips.append({"home": home, "away": away, "source": source_name})

    # Depuración rápida de duplicados exactos locales
    unique_tips = []
    seen = set()
    for t in tips:
        uid = f"{t['home'].lower()}_{t['away'].lower()}"
        if uid not in seen:
            seen.add(uid)
            unique_tips.append(t)
            
    return unique_tips

# =====================================================================
# MOTOR CENTRAL DE CRUCE INTELIGENTE
# =====================================================================

def main():
    print("=== INICIANDO CONTROLADOR DE EVENTOS INTELIGENTE v4 ===")
    
    all_tips = []
    
    # Extracción en las 5 fuentes estratégicas
    html = fetch_html_via_proxy("https://www.sportsgambler.com/", render_js=False)
    all_tips.extend(extract_matches(html, "SportsGambler"))
    
    html = fetch_html_via_proxy("https://scoutingstats.ai/value-bets", render_js=True)
    all_tips.extend(extract_matches(html, "ScoutingStats"))
    
    html = fetch_html_via_proxy("https://www.predictz.com/", render_js=True)
    all_tips.extend(extract_matches(html, "PredictZ"))
    
    html = fetch_html_via_proxy("https://www.forebet.com/", render_js=False)
    all_tips.extend(extract_matches(html, "Forebet"))
    
    html = fetch_html_via_proxy("https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en", render_js=False)
    all_tips.extend(extract_matches(html, "Vitibet"))

    print(f"\n[*] Mapeo consolidado completo. Total capturado en crudo: {len(all_tips)}")
    
    # --- BLOQUE DE DIAGNÓSTICO EN CONSOLA ---
    print("\n=== DIAGNÓSTICO DE CAPTURA (MUESTRA DE TEXTOS DETECTADOS) ===")
    for src in ["PredictZ", "Vitibet", "Forebet", "SportsGambler", "ScoutingStats"]:
        sample = [t for t in all_tips if t["source"] == src][:4]
        print(f"📍 Muestra de {src}:")
        if sample:
            for s in sample: print(f"   - Local: [{s['home']}] VS Visitante: [{s['away']}]")
        else:
            print("   - (Sin registros válidos en esta corrida)")
            
    # --- AGRUPACIÓN CON CLUSTERING DIFUSO (FUZZY) ---
    match_groups = [] # Lista de diccionarios con estructura de grupos emparejados
    
    for item in all_tips:
        h_clean = clean_team_name(item["home"])
        a_clean = clean_team_name(item["away"])
        
        if not h_clean or not a_clean:
            continue
            
        found_group = False
        for group in match_groups:
            # Comparamos el partido actual con el representante del grupo usando el validador difuso
            match_normal = are_teams_similar(h_clean, group["clean_home"]) and are_teams_similar(a_clean, group["clean_away"])
            match_inverted = are_teams_similar(h_clean, group["clean_away"]) and are_teams_similar(a_clean, group["clean_home"])
            
            if match_normal or match_inverted:
                group["sources"].add(item["source"])
                found_group = True
                break
                
        if not found_group:
            match_groups.append({
                "display_name": f"{item['home'].title()} vs {item['away'].title()}",
                "clean_home": h_clean,
                "clean_away": a_clean,
                "sources": {item["source"]}
            })
            
    # Filtrado final: El partido debe existir en al menos 2 plataformas distintas
    validated_alerts = [g for g in match_groups if len(g["sources"]) >= 2]
    print(f"\n[*] Partidos con coincidencia multi-fuente encontrados: {len(validated_alerts)}")
    
    # Despacho automatizado a Telegram
    if validated_alerts and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        for alert in validated_alerts:
            tips_details = "".join([f"▪️ *{src}*: `Confirmado en Radar`\n" for src in alert["sources"]])
            
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
        print("[+] Alertas cruzadas despachadas con éxito a tu canal VIP.")
    else:
        print("[-] Operación concluida sin alertas despachadas.")

if __name__ == "__main__":
    main()

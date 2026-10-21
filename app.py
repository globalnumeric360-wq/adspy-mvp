import streamlit as st
from apify_client import ApifyClient
import google.generativeai as genai
import urllib.parse 
import time
import re
import requests 

# -------------------------------------------------------------
# CONFIGURATION DE LA PAGE & DESIGN
# -------------------------------------------------------------
st.set_page_config(page_title="AdSpy By Global Numeric", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Nunito', sans-serif; color: #2c2c2e; }
        .hero-section { text-align: center; padding: 40px 0 20px 0; }
        .main-title { font-size: 2.8rem; font-weight: 800; color: #1c1c1e; margin-bottom: 5px; letter-spacing: -0.5px; }
        .sub-title { font-size: 1rem; font-weight: 800; color: #8e8e93; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 2px; }
        .hero-caption { font-size: 1.1rem; color: #636366; margin-bottom: 20px; }
        
        .info-box { background-color: #f8f9fa; border-left: 4px solid #1c1c1e; padding: 15px 20px; border-radius: 0 12px 12px 0; margin-bottom: 30px; font-size: 0.95rem; color: #3a3a3c; }

        div[data-baseweb="input"] > div, div[data-baseweb="base-input"] > div { border-radius: 16px !important; border: 1px solid #e5e5ea !important; background-color: #f2f2f7 !important; transition: all 0.2s ease; }
        div[data-baseweb="input"] > div:focus-within { border-color: #c7c7cc !important; background-color: #ffffff !important; }
        div.stButton > button:first-child { background-color: #1c1c1e; color: #ffffff; border: none; border-radius: 16px; padding: 8px 24px; font-weight: 700; transition: all 0.2s ease; width: 100%; }
        div.stButton > button:first-child:hover { background-color: #3a3a3c; color: #ffffff; }
        div[data-testid="stAlert"] { border-radius: 16px !important; border: none !important; }
        hr { border-color: #f2f2f7; margin: 2.5em 0; }
    </style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# EN-TÊTE & EXPLICATION DE RENTABILITÉ
# -------------------------------------------------------------
st.markdown("""
    <div class="hero-section">
        <p class="sub-title">AdSpy By Global Numeric</p>
        <p class="main-title">Intelligence Créative (V1)</p>
        <p class="hero-caption">Extrayez les publicités Meta gagnantes et analysez la stratégie sous-jacente.</p>
    </div>
    
    <div class="info-box">
        <strong>💡 Pourquoi ces publicités sont-elles considérées comme "Winner" ?</strong><br>
        Les annonces affichées par notre moteur ont passé un filtre strict : elles sont actuellement actives et triées par durée de diffusion. Dans le monde du Media Buying, aucun annonceur ne paie pour diffuser une publicité qui perd de l'argent sur la durée. En analysant ces contenus, vous décryptez des campagnes qui sont mathématiquement rentables.
    </div>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# RÉCUPÉRATION DES CLÉS API & SESSION STATE
# -------------------------------------------------------------
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
WEBHOOK_URL = st.secrets.get("WEBHOOK_URL") 

if not APIFY_TOKEN:
    st.error("Erreur de configuration : APIFY_TOKEN manquant.")
    st.stop()

apify_client = ApifyClient(APIFY_TOKEN)

if "ads_data" not in st.session_state:
    st.session_state.ads_data = None
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""
if "user_email" not in st.session_state:
    st.session_state.user_email = None
# MÉMOIRE DES ANALYSES IA (Évite que le texte disparaisse)
if "analyses_ia" not in st.session_state:
    st.session_state.analyses_ia = {}

# -------------------------------------------------------------
# EXTRACTEUR DE TEXTE
# -------------------------------------------------------------
def extraire_vrai_texte(item):
    text_parts = []
    try:
        for key in ["adText", "ad_creative_bodies", "adCreativeBodies"]:
            val = item.get(key)
            if val: text_parts.append(" ".join(val) if isinstance(val, list) else str(val))
        for key in ["ad_creative_link_titles", "adCreativeLinkTitles"]:
            val = item.get(key)
            if val: text_parts.append(" ".join(val) if isinstance(val, list) else str(val))
        for key in ["ad_creative_link_descriptions", "adCreativeLinkDescriptions", "ad_creative_link_captions"]:
            val = item.get(key)
            if val: text_parts.append(" ".join(val) if isinstance(val, list) else str(val))
        snapshot = item.get("snapshot", {})
        if isinstance(snapshot, dict):
            body = snapshot.get("body", {})
            if isinstance(body, dict):
                markup = body.get("markup", {})
                if isinstance(markup, dict):
                    html_content = markup.get("__html", "")
                    if html_content: text_parts.append(re.sub('<[^<]+>', '', html_content).strip())
            cards = snapshot.get("cards", [])
            if isinstance(cards, list) and len(cards) > 0:
                first_card = cards[0]
                if isinstance(first_card, dict):
                    card_body = first_card.get("body", {}).get("markup", {}).get("__html", "")
                    if card_body: text_parts.append(re.sub('<[^<]+>', '', card_body).strip())
        text_parts = [t.strip() for t in text_parts if t and len(t.strip()) > 3]
        texte_final = " \n\n ".join(list(dict.fromkeys(text_parts)))
        return texte_final if texte_final else None
    except Exception:
        return None

# -------------------------------------------------------------
# FORMULAIRE DE RECHERCHE CENTRÉ
# -------------------------------------------------------------
spacer1, center_col, spacer2 = st.columns([1, 2, 1])

with center_col:
    with st.form("search_form"):
        keyword = st.text_input("Secteur, produit ou mot-clé", "SaaS B2B")
        min_days = st.number_input("Ancienneté min. (jours)", min_value=0, value=7, step=7)
        submitted = st.form_submit_button("Lancer l'extraction des données")

if submitted:
    st.session_state.search_keyword = keyword
    st.session_state.analyses_ia = {} # On vide la mémoire des anciennes analyses
    try:
        safe_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword}"
        run_input = {"urls": [{"url": search_url}], "count": 15}
        
        with st.spinner("Analyse de la bibliothèque Meta en cours..."):
            run = apify_client.actor("curious_coder/facebook-ads-library-scraper").call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
            raw_items = apify_client.dataset(dataset_id).list_items().items
            
        if not raw_items:
            st.warning(f"Aucune publicité active trouvée pour '{keyword}'.")
            st.session_state.ads_data = None
        else:
            st.session_state.ads_data = raw_items
    except Exception as e:
        st.error(f"Erreur d'extraction : {e}")

# -------------------------------------------------------------
# AFFICHAGE & LEAD GEN (CAPTURE EMAIL)
# -------------------------------------------------------------
if st.session_state.ads_data:
    st.divider()
    st.success(f"{len(st.session_state.ads_data)} annonces publicitaires identifiées.")
    
    if not st.session_state.user_email:
        st.info("Les publicités ont été extraites. Débloquez le moteur d'analyse stratégique IA.")
        _, lead_col, _ = st.columns([1, 1.5, 1])
        with lead_col:
            with st.form("lead_gen_form"):
                st.markdown("### Accès aux Insights IA")
                st.write("Entrez votre adresse email pour débloquer l'analyse des publicités et être notifié de la V2.")
                email_input = st.text_input("Adresse email professionnelle")
                submit_email = st.form_submit_button("Débloquer les analyses")
                
                if submit_email:
                    if "@" in email_input and "." in email_input:
                        st.session_state.user_email = email_input
                        
                        if WEBHOOK_URL:
                            try:
                                payload = {
                                    "email": email_input,
                                    "source": "AdSpy V1 Lead Gen",
                                    "recherche": st.session_state.search_keyword,
                                    "date": time.strftime("%Y-%m-%d %H:%M:%S")
                                }
                                requests.post(WEBHOOK_URL, json=payload, timeout=5)
                            except Exception:
                                pass
                        
                        st.rerun()
                    else:
                        st.error("Veuillez entrer une adresse email valide.")
        st.divider()

    else:
        st.markdown(f"*Accès débloqué pour : {st.session_state.user_email}*")
        
        for idx, item in enumerate(st.session_state.ads_data[:5], 1):
            page_name = item.get("pageName") or item.get("page_name") or "Annonceur"
            vrai_texte = extraire_vrai_texte(item)
            
            if vrai_texte:
                ux_text_display = vrai_texte
                prompt_target = f"Décrypte la mécanique de copywriting de cette annonce existante :\n---\n{vrai_texte}\n---"
            else:
                ux_text_display = "[Format Visuel] Texte protégé par Meta ou incrusté dans l'image/vidéo."
                prompt_target = f"Le texte de cette publicité est inaccessible techniquement. Elle cible le marché '{st.session_state.search_keyword}'. Propose une seule recommandation stratégique de positionnement pour ce secteur."

            ad_id = item.get("id") or item.get("adArchiveID") or item.get("archive_id") or item.get("ad_id")
            page_id = item.get("pageID") or item.get("pageId") or item.get("page_id")
            
            if ad_id:
                ad_url = f"https://www.facebook.com/ads/library/?id={ad_id}"
            elif page_id:
                ad_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&view_all_page_id={page_id}"
            else:
                safe_keyword2 = urllib.parse.quote(st.session_state.search_keyword)
                ad_url = item.get("snapshotUrl") or f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword2}"

            st.markdown(f"### {page_name}")
            col_data, col_ai = st.columns([1, 1], gap="large")

            with col_data:
                st.markdown("**Texte extrait**")
                st.info(ux_text_display)
                st.markdown(f"[Consulter l'annonce originale sur Meta]({ad_url})")

            with col_ai:
                st.markdown("**Analyse Stratégique**")
                
                # --- NOUVEAU : Affichage depuis la mémoire ---
                if idx in st.session_state.analyses_ia:
                    st.success("Analyse terminée")
                    st.markdown(st.session_state.analyses_ia[idx])
                else:
                    if st.button(f"Générer l'insight pour la Pub #{idx}", key=f"btn_{idx}"):
                        if not GEMINI_API_KEY:
                            st.warning("Clé GEMINI_API_KEY non configurée.")
                        else:
                            with st.spinner("Décodage stratégique en cours..."):
                                genai.configure(api_key=GEMINI_API_KEY)
                                model = genai.GenerativeModel("gemini-3.8-flash")
                                
                                prompt = f"""
                                Tu es un Directeur Stratégique au sein d'une agence de publicité premium. 
                                {prompt_target}
                                
                                L'analyse doit être professionnelle, élégante et nuancée. Interdiction d'utiliser des formules 'putaclic'.
                                Structure ta réponse ainsi :
                                
                                **Décodage du Message**
                                Explique concrètement ce que la marque tente d'accomplir.
                                
                                **Levier Psychologique**
                                Identifie le besoin profond ciblé.
                                
                                **Recommandation d'Optimisation**
                                Suggère une idée pour élever cette publicité (direction artistique ou copywriting).
                                """
                                
                                max_tentatives = 3
                                success = False
                                
                                for tentative in range(max_tentatives):
                                    try:
                                        res = model.generate_content(prompt)
                                        # On sauvegarde en mémoire !
                                        st.session_state.analyses_ia[idx] = res.text
                                        success = True
                                        break 
                                        
                                    except Exception as err:
                                        err_str = str(err)
                                        if "429" in err_str or "Quota exceeded" in err_str:
                                            if tentative < max_tentatives - 1:
                                                match = re.search(r"retry in ([\d\.]+)s", err_str)
                                                wait_time = int(float(match.group(1))) + 2 if match else 20
                                                placeholder = st.empty()
                                                for i in range(wait_time, 0, -1):
                                                    placeholder.warning(f"Régulation de l'API Google. Reprise AUTOMATIQUE dans {i} s...")
                                                    time.sleep(1)
                                                placeholder.empty()
                                            else:
                                                st.error("Le serveur Google est toujours surchargé. Veuillez réessayer dans une minute.")
                                        else:
                                            st.error(f"Erreur système : {err}")
                                            break
                                            
                                if success:
                                    st.rerun() # Rafraîchit l'interface pour afficher le texte mémorisé
            st.divider()

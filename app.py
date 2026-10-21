import streamlit as st
from apify_client import ApifyClient
import google.generativeai as genai
import urllib.parse 
import time
import re

# -------------------------------------------------------------
# CONFIGURATION DE LA PAGE & DESIGN (UX APPLE / GLOBAL NUMERIC)
# -------------------------------------------------------------
st.set_page_config(page_title="AdSpy By Global Numeric", page_icon="🟣", layout="wide")

# Injection du CSS personnalisé pour le style Apple & couleurs Global Numeric
st.markdown("""
    <style>
        /* Typographie et espacements */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }
        
        /* Titre personnalisé */
        .main-title {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0px;
            letter-spacing: -1px;
        }
        .sub-title {
            font-size: 1.2rem;
            font-weight: 600;
            background: -webkit-linear-gradient(135deg, #E91E8C, #8B2FC9);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }

        /* Arrondis Apple sur les champs de saisie */
        div[data-baseweb="input"] > div, 
        div[data-baseweb="base-input"] > div {
            border-radius: 14px !important;
            border: 1px solid #e0e0e0;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
            transition: all 0.2s ease;
        }
        div[data-baseweb="input"] > div:focus-within {
            border-color: #8B2FC9 !important;
            box-shadow: 0 0 0 1px #8B2FC9 !important;
        }

        /* Boutons principaux avec dégradé Global Numeric */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #E91E8C, #8B2FC9);
            color: white;
            border: none;
            border-radius: 20px;
            padding: 8px 24px;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 10px rgba(139, 47, 201, 0.2);
        }
        div.stButton > button:first-child:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(233, 30, 140, 0.4);
        }

        /* Arrondis des boîtes d'alerte et de succès */
        div[data-testid="stAlert"] {
            border-radius: 16px !important;
            border: none !important;
            box-shadow: 0 2px 10px rgba(0,0,0,0.03);
        }
        
        /* Conteneurs et séparateurs plus doux */
        hr {
            border-color: #f0f0f0;
            margin: 2em 0;
        }
    </style>
""", unsafe_allow_html=True)

# En-tête de l'application
st.markdown('<p class="sub-title">AdSpy By Global Numeric</p>', unsafe_allow_html=True)
st.markdown('<p class="main-title">Intelligence Créative 🚀</p>', unsafe_allow_html=True)
st.caption("Extrayez les publicités Meta gagnantes et générez des concepts créatifs grâce à l'IA.")

# -------------------------------------------------------------
# RÉCUPÉRATION DES CLÉS API
# -------------------------------------------------------------
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if not APIFY_TOKEN:
    st.error("⚠️ Le token APIFY_TOKEN n'est pas configuré.")
    st.stop()

apify_client = ApifyClient(APIFY_TOKEN)

# Mémoire (Session State)
if "ads_data" not in st.session_state:
    st.session_state.ads_data = None
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""

# -------------------------------------------------------------
# FONCTIONS MÉTIER (Extracteur de texte)
# -------------------------------------------------------------
def extraire_vrai_texte(item):
    text_parts = []
    
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
        body = snapshot.get("body", {}).get("markup", {}).get("__html", "")
        if body: text_parts.append(re.sub('<[^<]+>', '', body).strip())
        
        cards = snapshot.get("cards", [])
        if isinstance(cards, list) and len(cards) > 0:
            card_body = cards[0].get("body", {}).get("markup", {}).get("__html", "")
            if card_body: text_parts.append(re.sub('<[^<]+>', '', card_body).strip())
            
    text_parts = [t.strip() for t in text_parts if t and len(t.strip()) > 3]
    texte_final = " \n\n ".join(list(dict.fromkeys(text_parts)))
    
    return texte_final if texte_final else None

# -------------------------------------------------------------
# FORMULAIRE & INTERFACE PRINCIPALE
# -------------------------------------------------------------
with st.form("search_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("Secteur, produit ou mot-clé :", "bain de bouche")
    with col2:
        min_days = st.number_input("Ancienneté min. (jours) :", min_value=0, value=7, step=7)
    
    submitted = st.form_submit_button("🔍 Lancer l'extraction")

if submitted:
    st.session_state.search_keyword = keyword
    
    try:
        safe_keyword = urllib.parse.quote(keyword)
        search_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword}"
        
        run_input = {
            "urls": [{"url": search_url}],
            "count": 15
        }
        
        with st.spinner(f"Scraping des publicités Meta pour '{keyword}' en cours..."):
            run = apify_client.actor("curious_coder/facebook-ads-library-scraper").call(run_input=run_input)
            dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
            raw_items = apify_client.dataset(dataset_id).list_items().items

        if not raw_items:
            st.warning(f"Aucune publicité trouvée pour le terme '{keyword}'.")
            st.session_state.ads_data = None
        else:
            st.session_state.ads_data = raw_items

    except Exception as e:
        st.error(f"Erreur d'extraction : {e}")

# -------------------------------------------------------------
# AFFICHAGE & MOTEUR D'ANALYSE IA
# -------------------------------------------------------------
if st.session_state.ads_data:
    st.success(f"🎯 {len(st.session_state.ads_data)} publicités identifiées avec succès !")
    st.divider()

    for idx, item in enumerate(st.session_state.ads_data[:5], 1):
        page_name = item.get("pageName") or item.get("page_name") or "Annonceur"
        vrai_texte = extraire_vrai_texte(item)
        
        if vrai_texte:
            ad_text_display = vrai_texte
            prompt_target = f"Analyse méticuleusement le texte (copywriting) de cette publicité :\n---\n{vrai_texte}\n---"
        else:
            ad_text_display = "📸 *Texte incrusté dans l'image ou la vidéo non lisible par le scraper.*"
            prompt_target = f"Cette publicité pour le produit '{st.session_state.search_keyword}' utilise un format 100% visuel sans description textuelle. Propose une stratégie d'accroche vidéo et un angle psychologique redoutable pour vendre ce type de produit."

        # Construction du lien propre
        ad_id = item.get("id") or item.get("adArchiveID") or item.get("archive_id") or item.get("ad_id")
        page_id = item.get("pageID") or item.get("pageId") or item.get("page_id")
        
        if ad_id:
            ad_url = f"https://www.facebook.com/ads/library/?id={ad_id}"
        elif page_id:
            ad_url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&view_all_page_id={page_id}"
        else:
            safe_keyword2 = urllib.parse.quote(st.session_state.search_keyword)
            ad_url = item.get("snapshotUrl") or f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&q={safe_keyword2}"

        st.markdown(f"### Pub #{idx} : **{page_name}**")
        
        col_data, col_ai = st.columns([1, 1], gap="large")

        with col_data:
            st.markdown("**📝 Copywriting extrait :**")
            st.info(ad_text_display)
            st.markdown(f"🔗 [**Ouvrir l'annonce dans Meta Ad Library**]({ad_url})")

        with col_ai:
            st.markdown("**🧠 Insight Global Numeric :**")
            if st.button(f"✨ Décoder la stratégie (Pub #{idx})", key=f"btn_{idx}"):
                if not GEMINI_API_KEY:
                    st.warning("⚠️ Clé GEMINI_API_KEY absente.")
                else:
                    try:
                        with st.spinner("Analyse du framework publicitaire..."):
                            genai.configure(api_key=GEMINI_API_KEY)
                            model = genai.GenerativeModel("gemini-3.8-flash")
                            
                            prompt = f"""
                            Tu es un copywriter et expert en Growth Marketing chez Global Numeric.
                            {prompt_target}
                            
                            Délivre une analyse percutante, moderne et minimaliste (en français) structurée ainsi :
                            1. **Hook (Accroche) :** Quel est le levier cognitif utilisé ?
                            2. **Angle & Persona :** Quel problème profond est ciblé ?
                            3. **Itération (V2) :** Propose une idée de script Hook rapide pour surpasser cette pub.
                            """
                            res = model.generate_content(prompt)
                            st.markdown(res.text)
                            
                    except Exception as err:
                        err_str = str(err)
                        if "429" in err_str or "Quota exceeded" in err_str:
                            match = re.search(r"retry in ([\d\.]+)s", err_str)
                            wait_time = int(float(match.group(1))) + 1 if match else 20
                            
                            placeholder = st.empty()
                            for i in range(wait_time, 0, -1):
                                placeholder.warning(f"⏳ L'IA calcule. Lancement possible dans **{i} secondes**...")
                                time.sleep(1)
                            placeholder.success("✅ C'est bon, l'IA est prête, cliquez à nouveau !")
                        else:
                            st.error(f"Erreur d'analyse : {err}")

        st.divider()

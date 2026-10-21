import streamlit as st
from apify_client import ApifyClient
import google.generativeai as genai
import urllib.parse 
import time
import re

# -------------------------------------------------------------
# CONFIGURATION DE LA PAGE & DESIGN MINIMALISTE (Zéro Emoji)
# -------------------------------------------------------------
st.set_page_config(page_title="AdSpy By Global Numeric", layout="wide")

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Nunito', sans-serif;
            color: #2c2c2e;
        }
        
        .main-title {
            font-size: 2.5rem;
            font-weight: 800;
            color: #1c1c1e;
            margin-bottom: 0px;
            letter-spacing: -0.5px;
        }
        .sub-title {
            font-size: 1rem;
            font-weight: 700;
            color: #8e8e93;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1.5px;
        }

        /* Champs de saisie - Soft UI */
        div[data-baseweb="input"] > div, 
        div[data-baseweb="base-input"] > div {
            border-radius: 16px !important;
            border: 1px solid #e5e5ea !important;
            background-color: #f2f2f7 !important;
            transition: all 0.2s ease;
        }
        div[data-baseweb="input"] > div:focus-within {
            border-color: #c7c7cc !important;
            background-color: #ffffff !important;
        }

        /* Boutons - Style Apple Light */
        div.stButton > button:first-child {
            background-color: #f2f2f7;
            color: #1c1c1e;
            border: 1px solid #e5e5ea;
            border-radius: 16px;
            padding: 8px 24px;
            font-weight: 700;
            transition: all 0.2s ease;
            box-shadow: none;
        }
        div.stButton > button:first-child:hover {
            background-color: #e5e5ea;
            border-color: #c7c7cc;
        }

        /* Conteneurs et typographie de contenu */
        div[data-testid="stAlert"] {
            border-radius: 16px !important;
            border: none !important;
        }
        
        hr {
            border-color: #f2f2f7;
            margin: 2.5em 0;
        }
        
        /* Styliser proprement la réponse IA */
        .ai-response-container {
            background-color: #ffffff;
            border: 1px solid #e5e5ea;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.02);
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="sub-title">AdSpy By Global Numeric</p>', unsafe_allow_html=True)
st.markdown('<p class="main-title">Intelligence Créative</p>', unsafe_allow_html=True)
st.caption("Extrayez les publicités Meta gagnantes et analysez la stratégie sous-jacente avec précision.")

# -------------------------------------------------------------
# RÉCUPÉRATION DES CLÉS API
# -------------------------------------------------------------
APIFY_TOKEN = st.secrets.get("APIFY_TOKEN")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if not APIFY_TOKEN:
    st.error("Erreur de configuration : APIFY_TOKEN manquant dans les variables d'environnement.")
    st.stop()

apify_client = ApifyClient(APIFY_TOKEN)

if "ads_data" not in st.session_state:
    st.session_state.ads_data = None
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""

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
# INTERFACE PRINCIPALE
# -------------------------------------------------------------
with st.form("search_form"):
    col1, col2 = st.columns([2, 1])
    with col1:
        keyword = st.text_input("Secteur, produit ou mot-clé", "SaaS B2B")
    with col2:
        min_days = st.number_input("Ancienneté min. (jours)", min_value=0, value=7, step=7)
    submitted = st.form_submit_button("Lancer l'extraction")

if submitted:
    st.session_state.search_keyword = keyword
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
# AFFICHAGE & ANALYSE STRATÉGIQUE IA
# -------------------------------------------------------------
if st.session_state.ads_data:
    st.success(f"{len(st.session_state.ads_data)} annonces publicitaires identifiées.")
    st.divider()

    for idx, item in enumerate(st.session_state.ads_data[:5], 1):
        page_name = item.get("pageName") or item.get("page_name") or "Annonceur"
        vrai_texte = extraire_vrai_texte(item)
        
        # Adaptation du Prompt pour un rôle de Directeur Stratégique (Premium, Sans putaclic)
        if vrai_texte:
            ux_text_display = vrai_texte
            prompt_target = f"Décrypte la mécanique de copywriting de cette annonce existante :\n---\n{vrai_texte}\n---"
        else:
            ux_text_display = "[Format Visuel] Texte protégé par Meta ou incrusté dans l'image/vidéo."
            prompt_target = f"Le texte de cette publicité est inaccessible techniquement. Sachant qu'elle cible le marché '{st.session_state.search_keyword}', propose une seule recommandation stratégique de positionnement (direction artistique ou angle d'attaque) pour ce type de secteur."

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
            if st.button(f"Générer l'insight pour la Pub #{idx}", key=f"btn_{idx}"):
                if not GEMINI_API_KEY:
                    st.warning("Clé GEMINI_API_KEY non configurée.")
                else:
                    try:
                        with st.spinner("Décodage stratégique en cours..."):
                            genai.configure(api_key=GEMINI_API_KEY)
                            model = genai.GenerativeModel("gemini-3.8-flash")
                            
                            prompt = f"""
                            Tu es un Directeur Stratégique au sein d'une agence de publicité premium. 
                            {prompt_target}
                            
                            L'analyse doit être extrêmement professionnelle, analytique, élégante et nuancée. Interdiction absolue d'utiliser des formules survendeuses ou 'putaclic'. 
                            
                            Structure ta réponse de cette manière claire et lisible :
                            
                            **Décodage du Message**
                            Explique concrètement ce que la marque tente d'accomplir ici.
                            
                            **Levier Psychologique**
                            Identifie le besoin profond ou le frein cognitif ciblé par cette annonce.
                            
                            **Recommandation d'Optimisation**
                            Suggère une seule idée précise pour élever cette publicité (direction artistique plus fine, copywriting plus élégant, ou recadrage du message).
                            """
                            res = model.generate_content(prompt)
                            
                            # Rendu de la réponse IA avec une belle structure Markdown
                            st.markdown(res.text)
                            
                    except Exception as err:
                        err_str = str(err)
                        if "429" in err_str or "Quota exceeded" in err_str:
                            match = re.search(r"retry in ([\d\.]+)s", err_str)
                            wait_time = int(float(match.group(1))) + 1 if match else 20
                            placeholder = st.empty()
                            for i in range(wait_time, 0, -1):
                                placeholder.warning(f"Régulation de l'API. Reprise possible dans {i} secondes.")
                                time.sleep(1)
                            placeholder.success("Le système est prêt pour une nouvelle analyse.")
                        else:
                            st.error(f"Erreur système : {err}")
        st.divider()

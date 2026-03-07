"""
=============================================================
  Générateur de sujets de Brevet Blanc – Technologie
  Collège Jacques Prévert – M. de PAZ
  Backend FastAPI – Déployé sur Railway
=============================================================
"""

import os, ftplib, io, subprocess, tempfile, datetime, json, re, asyncio
from collections import defaultdict
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="Générateur de Sujets – Technologie")

# ── CORS : autorise ton site à appeler ce backend ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Remplace * par l'URL de ton site si tu veux restreindre
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Variables d'environnement (à remplir dans Railway > Variables) ────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FTP_HOST           = os.environ.get("FTP_HOST", "")
FTP_USER           = os.environ.get("FTP_USER", "")
FTP_PASS           = os.environ.get("FTP_PASS", "")
FTP_REMOTE_PATH    = os.environ.get("FTP_REMOTE_PATH", "/sujets_generes/")
FTP_PUBLIC_URL     = os.environ.get("FTP_PUBLIC_URL", "")

# ── Rate limiting en mémoire : 3 générations max par IP par jour ─────────────
usage: dict = defaultdict(lambda: defaultdict(int))


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT SYSTÈME 
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = r"""
Tu es un expert en pédagogie technologique au collège en France (niveaux 4ème et 5ème).
Tu génères des sujets COMPLETS de brevet blanc de TECHNOLOGIE entièrement codés en LaTeX,
directement compilables avec pdflatex SANS ERREUR.

═══════════════════════════════════════════════
RÈGLES LATEX ABSOLUES (à respecter impérativement)
═══════════════════════════════════════════════

1. PACKAGES à déclarer dans le préambule (tous obligatoires) :
\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[french]{babel}
\usepackage[margin=1.8cm]{geometry}
\usepackage{amsmath}
\usepackage{array}
\usepackage{tabularx}
\usepackage{enumitem}
\usepackage{tikz}
\usepackage{graphicx}
\usepackage{xcolor}
\usepackage{etoolbox}
\usepackage[most,breakable]{tcolorbox}
\usetikzlibrary{shapes.geometric, arrows.meta, fit, calc, positioning}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.4em}

2. EN-TÊTE OBLIGATOIRE (toujours identique, mot pour mot) :
\begin{center}
{\small Technologie – 3\textsuperscript{ème} \hfill Collège – Sujet généré par IA}
\end{center}
\begin{center}
{\LARGE\bfseries [TITRE DU SUJET]}\\[0.3cm]
{\large Brevet Blanc – Épreuve de Technologie}\\[0.2cm]
{\normalsize Durée : 30 minutes \quad|\quad 25 points}
\end{center}
\begin{tabular}{p{5cm}p{5cm}p{5cm}}
\textbf{Nom :} \hrulefill & \textbf{Prénom :} \hrulefill & \textbf{Classe :} \hrulefill
\end{tabular}
\vspace{0.5cm}

3. RÈGLES TikZ STRICTES pour éviter les débordements :
- Toujours utiliser [node distance=1.5cm] minimum
- Largeur maximale d'un nœud : minimum width=2.8cm, maximum width=3.5cm
- Texte dans les nœuds : toujours align=center, font=\footnotesize\sffamily
- Limiter les schémas à 5-6 nœuds maximum
- Toujours envelopper le tikzpicture dans \begin{center}...\end{center}
- Ne JAMAIS mettre de texte accentué directement dans TikZ : utiliser \'{e}, \`{a}, \^{o} etc.
- Pour les schémas à compléter : utiliser des nœuds vides avec \node[composant] (X) at (0,0) {};
- Utiliser des couleurs si besoin dans les schémas

4. TABLEAUX : toujours utiliser tabularx avec \linewidth, jamais tabular seul.

═══════════════════════════════════════════════
STRUCTURE OBLIGATOIRE DU SUJET
═══════════════════════════════════════════════

──── PARTIE 1 : DOCUMENTS ────

[En-tête + titre + champs élève]
[Contexte introductif 3-5 lignes]

\subsection*{Document 1 -- [Titre descriptif du principe de fonctionnement]}
Texte de présentation + schéma TikZ (chaîne fonctionnelle ou schéma blocs)

\subsection*{Document 2 -- [Titre descriptif]}
Tableau comparatif de matériaux ou composants (tabularx, 3-4 colonnes, 3-4 lignes)

\subsection*{Document 3 -- [Titre descriptif]}
Données numériques pour un calcul (formule + valeurs données)

\subsection*{Document 4 -- [Titre descriptif de l'algorigramme]}
Algorigramme TikZ complet

\newpage

Dans tous les cas, la partie 1 peut prendre autant de page que nécessaire pour que les schémas et algorigrammes rentrent sans se chevaucher.

──── PARTIE 2 : QUESTIONS ────

\begin{center}
\rule{\linewidth}{2pt}\\[0.3cm]
{\Large\bfseries QUESTIONS}\\[0.1cm]
\rule{\linewidth}{2pt}
\end{center}
\vspace{0.3cm}

Chaque question OBLIGATOIREMENT dans ce format exact :
\noindent\textbf{Question X -- [titre court]} \hfill \textit{(Y points)}\\[0.1cm]
[énoncé]
\begin{tcolorbox}[colback=gray!5, colframe=gray!50, breakable, left=4pt, right=4pt, top=4pt, bottom=VALEUR]
\end{tcolorbox}
\vspace{0.4cm}

Valeurs bottom selon la question :
- Question courte (2-3 pts) : bottom=35pt
- Question développée (4-5 pts) : bottom=55pt
- Question calcul : bottom=70pt avec lignes de calcul (\rule{\linewidth}{0.3pt}\\[0.6cm] répété 4 fois)
- Question schéma à compléter : insérer le TikZ du schéma À COMPLÉTER dans la tcolorbox (nœuds vides)

\newpage

──── PARTIE 3 : CORRECTION ENSEIGNANT ────

\begin{center}
\rule{\linewidth}{2pt}\\[0.3cm]
{\Large\bfseries CORRIGÉ ET BARÈME -- RÉSERVÉ À L'ENSEIGNANT}\\[0.1cm]
\rule{\linewidth}{2pt}
\end{center}

Pour chaque question : réponse attendue + critères de notation précis.

═══════════════════════════════════════════════
TYPES D'EXERCICES À VARIER (choisir 5 parmi ces types, un par question)
═══════════════════════════════════════════════

TYPE A – ANALYSE FONCTIONNELLE
Compléter un diagramme des blocs internes (chaîne d'information + chaîne d'énergie).
→ Schéma TikZ avec nœuds vides à remplir, liste de termes fournie à replacer.
Termes possibles : Acquérir, Traiter, Communiquer, Alimenter, Distribuer, Convertir.

TYPE B – MATÉRIAUX ET PROPRIÉTÉS
Choisir un matériau à partir d'un tableau + justifier avec 3 critères du cahier des charges.
→ Tableau tabularx + espace de réponse structuré (matériau choisi + 3 lignes argumentées).

TYPE C – CALCUL NUMÉRIQUE
Appliquer une formule donnée (énergie E=P×t, puissance P=U×I, capacité Q=I×t, etc.)
→ Espace calcul avec lignes + unités attendues.

TYPE D – ALGORIGRAMME
- Soit compléter un algorigramme à trous (mots-clés manquants : SI, SINON, condition, action)
- Soit lire un algorigramme et décrire en français ce qu'il fait
→ Algorigramme TikZ + zone réponse.

TYPE E – PROGRAMMATION / ALGORITHME TEXTUEL
Compléter un algorithme en pseudo-code ou Scratch-like avec des pointillés.
Thèmes : capteur, condition, boucle, variable, ordre envoyé à un actionneur.
Exemple de structure à compléter :
Répéter jusqu'à (fin de mission)
|  Lire valeur du capteur de .........
|  SI ( valeur > ......... ) ALORS
|  |  Activer .........
|  SINON
|  |  .........
|  FIN SI
Fin Répéter

TYPE F – DÉVELOPPEMENT DURABLE / CYCLE DE VIE
Identifier la phase du cycle de vie (fabrication, utilisation, fin de vie) concernée.
Relier matériau et impact environnemental à partir du tableau document 2.

TYPE G – LECTURE DE SCHÉMA / IDENTIFICATION
Identifier des composants sur un schéma fonctionnel TikZ annoté partiellement.
Relier composant ↔ fonction (Acquérir / Traiter / Communiquer / Convertir).

TYPE H – AVANTAGES / INCONVÉNIENTS / USAGE
Citer 2 avantages et 1 limite du système étudié. Justifier à partir du contexte.

═══════════════════════════════════════════════
CONTRAINTES FINALES
═══════════════════════════════════════════════
- Total barème = exactement 25 points
- Niveau : 3ème (collège)
- Langue : français intégral
- PAS d'images externes, TOUT en TikZ ou tabularx
- Varier les thèmes ET les types d'exercices à chaque génération

THÈMES (varier obligatoirement à chaque appel) :
Robot aspirateur, Fontaine connectée, Vélo électrique, Serrure connectée,
Lampadaire solaire intelligent, Serre automatisée, Trottinette électrique,
Purificateur d'air, Bras robotisé pédagogique, Porte automatique,
Système d'irrigation, Voiture autonome miniature, Pont-levis connecté,
Distributeur automatique de gel, Capteur de température connecté. Tu peux envisager d'autres thèmes qui ne sont pas dans la liste.

RÉPONDS UNIQUEMENT avec le code LaTeX complet.
Commence par \documentclass et termine par \end{document}.
Zéro texte avant ni après.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  APPEL GroqCloud
# ─────────────────────────────────────────────────────────────────────────────
async def call_gemini(theme_hint: str = "") -> str:
    user_message = (
        "Génère un sujet de brevet blanc de technologie complet en LaTeX."
        + (f" Thème : {theme_hint}." if theme_hint else " Choisis un thème varié.")
        + " Le code doit être directement compilable avec pdflatex sans erreur."
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_message}
                ],
                "temperature": 0.75,
                "max_tokens": 8192,
            }
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"Erreur Groq ({resp.status_code}): {resp.text[:500]}")

    raw = resp.json()["choices"][0]["message"]["content"]
    raw = re.sub(r"^```(?:latex)?\s*\n?", "", raw.strip())
    raw = re.sub(r"\n?```\s*$", "", raw.strip())
    return raw.strip()
# ─────────────────────────────────────────────────────────────────────────────
#  NETTOYAGE LATEX
# ─────────────────────────────────────────────────────────────────────────────
def fix_latex(latex_code: str) -> str:
    """Corrige les erreurs LaTeX courantes générées par le LLM."""
    lines = latex_code.split("\n")
    fixed = []
    in_tikz = False
    for line in lines:
        if "\\begin{tikzpicture}" in line:
            in_tikz = True
        if "\\end{tikzpicture}" in line:
            in_tikz = False
            fixed.append(line)
            continue
        # N'échappe les _ que hors des environnements TikZ et math
        if not in_tikz and "$" not in line and "verb" not in line and "\\texttt" not in line:
            line = re.sub(r"(?<!\\)_", r"\\_", line)
        fixed.append(line)
    return "\n".join(fixed)

# ─────────────────────────────────────────────────────────────────────────────
#  COMPILATION LATEX → PDF
# ─────────────────────────────────────────────────────────────────────────────
def compile_latex(latex_code: str) -> bytes:
    """Compile le LaTeX avec pdflatex et retourne les octets du PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, "sujet.tex")
        pdf_path = os.path.join(tmpdir, "sujet.pdf")

        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(latex_code)

        # Deux passes pour résoudre les références internes
        log = ""
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                capture_output=True, timeout=60
            )
            log = result.stdout.decode("utf-8", errors="replace")

        if not os.path.exists(pdf_path):
            raise HTTPException(
                500,
                f"Échec de la compilation LaTeX.\n\nLog (fin) :\n{log[-2000:]}"
            )

        with open(pdf_path, "rb") as f:
            return f.read()


# ─────────────────────────────────────────────────────────────────────────────
#  UPLOAD FTP
# ─────────────────────────────────────────────────────────────────────────────
def upload_ftp(pdf_bytes: bytes, filename: str) -> str:
    """Envoie le PDF sur le FTP. Retourne l'URL publique ou chaîne vide."""
    if not FTP_HOST:
        return ""
    try:
        with ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS) as ftp:
            ftp.cwd(FTP_REMOTE_PATH)
            ftp.storbinary(f"STOR {filename}", io.BytesIO(pdf_bytes))
        return f"{FTP_PUBLIC_URL.rstrip('/')}/{filename}"
    except Exception as e:
        print(f"[FTP] Erreur : {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  SAUVEGARDE NOTION
# ─────────────────────────────────────────────────────────────────────────────
async def save_to_notion(theme: str, filename: str, ftp_url: str, ip: str):
    """Crée une entrée dans la base Notion (colonnes à créer au préalable)."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        return

    now = datetime.datetime.now(datetime.timezone.utc)
    properties = {
        "Nom du fichier": {
            "title": [{"text": {"content": filename}}]
        },
        "Thème": {
            "rich_text": [{"text": {"content": theme or "Aléatoire"}}]
        },
        "Date de génération": {
            "date": {"start": now.isoformat()}
        },
        "IP anonymisée": {
            "rich_text": [{"text": {"content": ip[:8] + "***"}}]
        },
        "URL FTP": {
            "url": ftp_url if ftp_url else None
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {NOTION_API_KEY}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28",
            },
            json={
                "parent": {"database_id": NOTION_DATABASE_ID},
                "properties": properties,
            }
        )
    if resp.status_code not in (200, 201):
        print(f"[Notion] Erreur {resp.status_code}: {resp.text[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {
        "status": "ok",
        "service": "Générateur Sujets Techno",
        "college": "Collège Jacques Prévert"
    }


@app.post("/generer")
async def generer_sujet(request: Request):
    """
    Endpoint principal appelé par le widget sur le site.
    Body JSON optionnel : { "theme": "Robot aspirateur" }
    Retourne le PDF en téléchargement direct.
    """

    # 1. Rate limiting ─────────────────────────────────────────────────────
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 7:
        raise HTTPException(
            429,
            "Limite atteinte : 3 sujets par jour par adresse IP. Reviens demain !"
        )

    # 2. Lecture du thème optionnel ────────────────────────────────────────
    try:
        body = await request.json()
        theme = str(body.get("theme", "")).strip()[:80]
    except Exception:
        theme = ""

    # 3. Génération LaTeX via Gemini ───────────────────────────────────────
    latex_code = await call_gemini(theme)

    # 3b. Nettoyage du LaTeX ───────────────────────────────────────────────
    latex_code = fix_latex(latex_code)

    # 4. Compilation PDF ───────────────────────────────────────────────────
    pdf_bytes = compile_latex(latex_code)

    # 5. Nommage du fichier ────────────────────────────────────────────────
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_theme = re.sub(r"[^a-zA-Z0-9]", "_", theme)[:30] if theme else "aleatoire"
    filename = f"brevet_blanc_{safe_theme}_{ts}.pdf"

    # 6. Upload FTP (non bloquant) ─────────────────────────────────────────
    ftp_url = await asyncio.to_thread(upload_ftp, pdf_bytes, filename)

    # 7. Sauvegarde Notion (fire and forget) ───────────────────────────────
    asyncio.create_task(save_to_notion(theme or "Aléatoire", filename, ftp_url, client_ip))

    # 8. Retourne le PDF ───────────────────────────────────────────────────
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Generated-Theme": theme or "aleatoire",
        }
    )


@app.get("/latex")
async def obtenir_latex_brut(theme: str = ""):
    """Route de débogage : retourne le LaTeX brut sans compiler."""
    latex_code = await call_gemini(theme)
    latex_code = fix_latex(latex_code)
    return JSONResponse({"latex": latex_code, "longueur": len(latex_code)})

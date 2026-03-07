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

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ── Variables d'environnement ─────────────────────────────────────────────────
NOTION_API_KEY     = os.environ.get("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")
GROQ_API_KEY       = os.environ.get("GROQ_API_KEY", "")
FTP_HOST           = os.environ.get("FTP_HOST", "")
FTP_USER           = os.environ.get("FTP_USER", "")
FTP_PASS           = os.environ.get("FTP_PASS", "")
FTP_REMOTE_PATH    = os.environ.get("FTP_REMOTE_PATH", "/sujets_generes/")
FTP_PUBLIC_URL     = os.environ.get("FTP_PUBLIC_URL", "")

# ── Rate limiting ─────────────────────────────────────────────────────────────
usage: dict = defaultdict(lambda: defaultdict(int))


# ─────────────────────────────────────────────────────────────────────────────
#  PROMPT SYSTÈME
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = r"""
Tu es un expert en pédagogie technologique au collège en France (niveau 3ème).
Tu génères des sujets COMPLETS de brevet blanc de TECHNOLOGIE entièrement codés en LaTeX,
directement compilables avec pdflatex SANS ERREUR.

═══════════════════════════════════════════════
RÈGLES LATEX ABSOLUES
═══════════════════════════════════════════════

1. PRÉAMBULE OBLIGATOIRE (copier exactement) :
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
\usepackage[framemethod=default]{mdframed}
\usetikzlibrary{shapes.geometric, arrows.meta, fit, calc, positioning}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.6em}
\usepackage{needspace}

2. BOÎTES DE RÉPONSE : utiliser UNIQUEMENT ce format (jamais tcolorbox) :
\begin{mdframed}[linecolor=black!40, linewidth=0.6pt, innerleftmargin=6pt, innerrightmargin=6pt, innertopmargin=4pt, innerbottommargin=VALEUR]
\end{mdframed}

Valeurs innerbottommargin selon la question :
- Question courte (2-3 pts) : innerbottommargin=35pt
- Question développée (4-5 pts) : innerbottommargin=55pt
- Question calcul : innerbottommargin=70pt, avec 4 lignes de calcul à l'intérieur :
  \rule{\linewidth}{0.3pt}\\[0.6cm]
  \rule{\linewidth}{0.3pt}\\[0.6cm]
  \rule{\linewidth}{0.3pt}\\[0.6cm]
  \rule{\linewidth}{0.3pt}\\[0.6cm]
- Question schéma à compléter : insérer le TikZ à compléter à l'intérieur

3. RÈGLES TikZ STRICTES :
- Toujours [node distance=1.5cm] minimum
- Largeur nœud : minimum width=2.8cm, maximum width=3.5cm
- Texte nœuds : align=center, font=\footnotesize\sffamily
- Maximum 5-6 nœuds par schéma
- Toujours dans \begin{center}...\end{center}
- JAMAIS de texte accentué dans TikZ : utiliser \'{e}, \`{a}, \^{o} etc.
- Nœuds vides pour schémas à compléter : \node[style] (X) at (0,0) {};

4. TABLEAUX : toujours tabularx avec \linewidth.

5. INTERDICTIONS ABSOLUES :
- Ne jamais utiliser \tcolorbox ni aucun package de couleur (xcolor, color)
- Ne jamais mettre \newpage à l'intérieur d'un environnement mdframed
- Ne jamais utiliser _ hors mode mathématique (utiliser \_ ou éviter)

═══════════════════════════════════════════════
STRUCTURE OBLIGATOIRE
═══════════════════════════════════════════════

──── EN-TÊTE (toujours identique) ────

\begin{center}
{\small Technologie -- 3\textsuperscript{\`eme} \hfill Coll\`ege -- Sujet g\'en\'er\'e par IA}
\end{center}
\begin{center}
{\LARGE\bfseries [TITRE DU SUJET]}\\[0.3cm]
{\large Brevet Blanc -- \'Epreuve de Technologie}\\[0.2cm]
{\normalsize Dur\'ee : 30 minutes \quad|\quad 25 points}
\end{center}
\begin{tabularx}{\linewidth}{XXX}
\textbf{Nom :} \hrulefill & \textbf{Pr\'enom :} \hrulefill & \textbf{Classe :} \hrulefill
\end{tabularx}
\vspace{0.5cm}

──── PARTIE 1 : DOCUMENTS ────

[Contexte introductif 5-8 lignes, très détaillé : décrire le système, son utilité, ses composants principaux, son contexte d'usage réel]

\subsection*{Document 1 -- [Titre très descriptif]}
Texte de présentation DÉTAILLÉ (5-8 lignes) décrivant précisément le fonctionnement du système.
Puis schéma TikZ COMPLET de la chaîne fonctionnelle avec TOUS les blocs :
- Chaîne d'information : Acquérir → Traiter → Communiquer
- Chaîne d'énergie : Alimenter → Distribuer → Convertir
- Relier les deux chaînes avec des flèches
- Chaque nœud doit contenir le nom du composant réel (ex: "Capteur DHT22" pas juste "Capteur")
- Minimum 6 nœuds, maximum 8 nœuds
Si le schéma est grand, ajouter \newpage avant le document suivant.

\newpage

\subsection*{Document 2 -- [Titre très descriptif]}
Tableau comparatif DÉTAILLÉ tabularx (4-5 colonnes, 4-5 lignes).
Chaque cellule doit contenir des données réelles et précises (valeurs chiffrées, unités, caractéristiques techniques).
Ajouter 3-4 lignes de texte explicatif APRÈS le tableau pour contextualiser les données.

\newpage

\subsection*{Document 3 -- [Titre très descriptif]}
Données numériques COMPLÈTES pour un calcul :
- Présenter le contexte en 3-4 lignes
- Donner la formule avec explication de chaque variable
- Donner toutes les valeurs numériques avec unités
- Poser la question de calcul clairement

\newpage

\subsection*{Document 4 -- [Titre très descriptif de l'algorigramme]}
Texte d'introduction de l'algorigramme (3-4 lignes).
Algorigramme TikZ COMPLET et DÉTAILLÉ :
- Minimum 8 étapes (Début, 2-3 conditions SI/SINON, 3-4 actions, Fin)
- Chaque nœud avec texte explicite et composant réel nommé
- Utiliser des formes distinctes : rectangle pour actions, losange pour conditions, ovale pour Début/Fin
- Flèches étiquetées OUI/NON sur les conditions

\newpage

──── PARTIE 2 : QUESTIONS ────

\begin{center}
\rule{\linewidth}{2pt}\\[0.3cm]
{\Large\bfseries QUESTIONS}\\[0.1cm]
\rule{\linewidth}{2pt}
\end{center}
\vspace{0.3cm}

Format obligatoire pour chaque question :
\noindent\textbf{Question X -- [titre court]} \hfill \textit{(Y points)}\\[0.1cm]
[énoncé de la question]
\begin{mdframed}[linecolor=black!40, linewidth=0.6pt, innerleftmargin=6pt, innerrightmargin=6pt, innertopmargin=4pt, innerbottommargin=VALEUR]
\end{mdframed}
\vspace{0.4cm}

\newpage

──── PARTIE 3 : CORRIGÉ ────

\begin{center}
\rule{\linewidth}{2pt}\\[0.3cm]
{\Large\bfseries CORRIG\'E ET BAR\`EME -- R\'ESERV\'E \`A L'ENSEIGNANT}\\[0.1cm]
\rule{\linewidth}{2pt}
\end{center}

Pour chaque question : réponse attendue + critères de notation.

═══════════════════════════════════════════════
TYPES D'EXERCICES (choisir 5 parmi ces types)
═══════════════════════════════════════════════

TYPE A – ANALYSE FONCTIONNELLE
Compléter un diagramme des blocs (chaîne d'information + chaîne d'énergie).
Schéma TikZ avec nœuds vides, liste de termes à replacer.
Termes : Acquérir, Traiter, Communiquer, Alimenter, Distribuer, Convertir.

TYPE B – MATÉRIAUX ET PROPRIÉTÉS
Choisir un matériau depuis un tableau + justifier avec 3 critères.
Tableau tabularx + espace de réponse structuré.

TYPE C – CALCUL NUMÉRIQUE
Appliquer une formule (E=P*t, P=U*I, Q=I*t, etc.)
Espace calcul avec lignes + unités attendues.

TYPE D – ALGORIGRAMME
Compléter un algorigramme à trous OU décrire en français ce qu'il fait.
Algorigramme TikZ + zone réponse.

TYPE E – PROGRAMMATION / ALGORITHME TEXTUEL
Compléter un pseudo-code avec des pointillés.
Thèmes : capteur, condition, boucle, variable, actionneur.

TYPE F – DÉVELOPPEMENT DURABLE / CYCLE DE VIE
Identifier la phase du cycle de vie concernée.
Relier matériau et impact environnemental.

TYPE G – LECTURE DE SCHÉMA
Identifier des composants sur un schéma TikZ annoté partiellement.
Relier composant et fonction.

TYPE H – AVANTAGES / INCONVÉNIENTS
Citer 2 avantages et 1 limite du système. Justifier.

═══════════════════════════════════════════════
CONTRAINTES FINALES
═══════════════════════════════════════════════
- Total barème = exactement 25 points
- Niveau : 3ème (collège)
- Langue : français intégral
- PAS d'images externes, TOUT en TikZ ou tabularx
- Varier les thèmes ET les types d'exercices à chaque génération
- Chaque document doit occuper AU MINIMUM une demi-page
- Les schémas TikZ doivent être grands et lisibles (scale=1.2 minimum)
- Les algorigrammes doivent avoir minimum 8 étapes
- Les tableaux doivent avoir minimum 4 colonnes et 4 lignes avec données réelles
- Utiliser \vspace{0.5cm} généreusement entre les éléments
- Utiliser \newpage entre chaque document pour garantir la lisibilité
- Nommer les composants avec leurs références réelles (Arduino, DHT22, L293D, etc.)

THÈMES (varier à chaque appel) :
Robot aspirateur, Fontaine connectée, Vélo électrique, Serrure connectée,
Lampadaire solaire intelligent, Serre automatisée, Trottinette électrique,
Purificateur d'air, Bras robotisé pédagogique, Porte automatique,
Système d'irrigation, Voiture autonome miniature, Pont-levis connecté,
Distributeur automatique de gel, Capteur de température connecté.
Tu peux choisir d'autres thèmes non listés.

RÉPONDS UNIQUEMENT avec le code LaTeX complet.
Commence par \documentclass et termine par \end{document}.
Zéro texte avant ni après.
"""


# ─────────────────────────────────────────────────────────────────────────────
#  APPEL GROQCLOUD
# ─────────────────────────────────────────────────────────────────────────────
async def call_groq(theme_hint: str = "") -> str:
    user_message = (
        "Génère un sujet de brevet blanc de technologie complet en LaTeX."
        + (f" Thème : {theme_hint}." if theme_hint else " Choisis un thème varié.")
        + " Le code doit être directement compilable avec pdflatex sans erreur."
        + " N'utilise jamais tcolorbox ni xcolor. Utilise uniquement mdframed pour les boîtes."
    )

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
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

    # 1. Supprimer tout ce qui précède \documentclass
    match = re.search(r"\\documentclass", latex_code)
    if match:
        latex_code = latex_code[match.start():]

    # 2. S'assurer que \begin{document} est présent
    if "\\begin{document}" not in latex_code:
        # L'injecter juste après la dernière ligne de préambule (\usepackage, \usetikz, \setlength)
        lines = latex_code.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("\\") and any(k in line for k in [
                "\\usepackage", "\\usetikz", "\\setlength", "\\documentclass", "\\newcommand"
            ]):
                insert_at = i
        lines.insert(insert_at + 1, "\\begin{document}")
        latex_code = "\n".join(lines)

    # 3. S'assurer que \end{document} est présent
    if "\\end{document}" not in latex_code:
        latex_code += "\n\\end{document}"

    # 4. Supprimer tcolorbox et xcolor résiduels
    latex_code = re.sub(r"\\usepackage\[.*?\]\{tcolorbox\}", "", latex_code)
    latex_code = re.sub(r"\\usepackage\{tcolorbox\}", "", latex_code)
    latex_code = re.sub(r"\\usepackage(\[.*?\])?\{xcolor\}", "", latex_code)
    latex_code = re.sub(r"\\usepackage(\[.*?\])?\{color\}", "", latex_code)

    # 5. Remplacer les tcolorbox résiduelles par mdframed
    latex_code = re.sub(
        r"\\begin\{tcolorbox\}(\[.*?\])?",
        r"\\begin{mdframed}[linecolor=black!40, linewidth=0.6pt, innerleftmargin=6pt, innerrightmargin=6pt, innertopmargin=4pt, innerbottommargin=40pt]",
        latex_code
    )
    latex_code = re.sub(r"\\end\{tcolorbox\}", r"\\end{mdframed}", latex_code)

    # 6. Traitement ligne par ligne
    lines = latex_code.split("\n")
    fixed = []
    in_tikz = False
    in_mdframed = False
    pending_newpage = False

    for line in lines:
        if "\\begin{tikzpicture}" in line:
            in_tikz = True
        if "\\end{tikzpicture}" in line:
            in_tikz = False
            fixed.append(line)
            continue

        if "\\begin{mdframed}" in line:
            in_mdframed = True

        if "\\end{mdframed}" in line:
            in_mdframed = False
            fixed.append(line)
            if pending_newpage:
                fixed.append("\\newpage")
                pending_newpage = False
            continue

        if in_mdframed and "\\newpage" in line:
            pending_newpage = True
            continue

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

        log = ""
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, tex_path],
                capture_output=True, timeout=60
            )
            log = result.stdout.decode("utf-8", errors="replace")

        if not os.path.exists(pdf_path):
            # Extraire uniquement les lignes d'erreur (commençant par !)
            error_lines = [l for l in log.split("\n") if l.startswith("!") or l.startswith("l.")]
            error_summary = "\n".join(error_lines[:30]) if error_lines else log[-3000:]
            raise HTTPException(
                500,
                f"Échec de la compilation LaTeX.\n\nErreurs détectées :\n{error_summary}"
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
    """Crée une entrée dans la base Notion."""
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
    Endpoint principal appelé par le widget.
    Body JSON optionnel : { "theme": "Robot aspirateur" }
    Retourne le PDF en téléchargement direct.
    """

    # 1. Rate limiting
    client_ip = request.client.host
    today = datetime.date.today().isoformat()
    usage[today][client_ip] += 1
    if usage[today][client_ip] > 7:
        raise HTTPException(
            429,
            "Limite atteinte : 7 sujets par jour par adresse IP. Reviens demain !"
        )

    # 2. Lecture du thème optionnel
    try:
        body = await request.json()
        theme = str(body.get("theme", "")).strip()[:80]
    except Exception:
        theme = ""

    # 3. Génération LaTeX via Groq
    latex_code = await call_groq(theme)

    # 4. Nettoyage du LaTeX
    latex_code = fix_latex(latex_code)

    # 5. Compilation PDF
    pdf_bytes = compile_latex(latex_code)

    # 6. Nommage du fichier
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_theme = re.sub(r"[^a-zA-Z0-9]", "_", theme)[:30] if theme else "aleatoire"
    filename = f"brevet_blanc_{safe_theme}_{ts}.pdf"

    # 7. Upload FTP (non bloquant)
    ftp_url = await asyncio.to_thread(upload_ftp, pdf_bytes, filename)

    # 8. Sauvegarde Notion (fire and forget)
    asyncio.create_task(save_to_notion(theme or "Aléatoire", filename, ftp_url, client_ip))

    # 9. Retourne le PDF
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
    latex_code = await call_groq(theme)
    latex_code = fix_latex(latex_code)
    return JSONResponse({"latex": latex_code, "longueur": len(latex_code)})

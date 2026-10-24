# Projet final — Web Sémantique : Éducation & Formation

**Conforme aux fonctionnalités demandées dans le courriel de Maha MALLEK** : ontologie OWL/RDF, propriétés, individus, axiomes, interfaces frontend/backend, SPARQL CRUD/recherche/filtrage, communication API, et traduction de questions françaises en SPARQL avec spaCy (sans API LLM).

## Installation Windows (PowerShell)

Pré-requis : Python 3.11 ou 3.12 conseillé, Node.js 20+.

### Terminal 1 — backend

```powershell
cd C:\Users\Amine\Desktop\WebSemantique\EducationFormation_Final
py -m pip install -r requirements.txt
py -m uvicorn backend:app --reload
```

Ouvrir http://127.0.0.1:8000/docs pour tester les endpoints.

### Terminal 2 — frontend

```powershell
cd C:\Users\Amine\Desktop\WebSemantique\EducationFormation_Final\frontend
npm install
npm run dev
```

Ouvrir http://localhost:5173 (ou http://127.0.0.1:5173).

**Important** : placez le dossier où vous le souhaitez et adaptez le chemin `cd`. Ne copiez pas ce projet dans votre ancien dossier sans sauvegarde.

## Fonctions à démontrer

1. **Ontologie** : 16 classes, ObjectProperties, DataProperties, individus et axiomes existants, affichés dans l'onglet Ontologie.
2. **SPARQL SELECT** : listes d'étudiants, enseignants et cours.
3. **SPARQL recherche/filtrage** : `GET /cours?search=algo` et `GET /cours?starts_with=Prog`.
4. **CRUD** : POST /cours, PUT /cours/{nom}, DELETE /cours/{nom}; interface React dans « Cours ».
5. **Communication** : React appelle FastAPI via HTTP et affiche les réponses.
6. **NLP** : « Quels sont les étudiants ? » → détection de l'intention `students` → requête SPARQL → réponse `Amine`. Essayer enseignants, cours, formations, modules, compétences, évaluations, ressources, certifications.

### NLP : outil et limites à expliquer au jury

- **spaCy** : `spacy.blank('fr')` pour la tokenisation française (aucun modèle pré-entraîné nécessaire).
- **Règles locales** : normalisation des accents, synonymes et détection d'intention.
- **Générateur de templates SPARQL** : transforme l'intention détectée en une requête `SELECT` exécutable.
- **RDFLib** : exécute la requête sur l'ontologie.
- **Pas de LLM** ni de prompt engineering avec API distante.
- **Limite honnête** : démonstrateur de NLP à intentions prédéfinies, pas un traducteur universel de questions en SPARQL. Les questions inconnues produisent une erreur explicite.

## Persistance et sauvegarde

Le fichier original `copy_antologie.rdf` reste inchangé. Le premier CRUD écrit dans `ontology_working.rdf`, rechargé aux démarrages suivants. Pour revenir à l'ontologie initiale, arrêter FastAPI puis supprimer `ontology_working.rdf` (cela efface les modifications faites via l'interface).

## Tests

```powershell
py -m pytest tests -q
```

Les tests valident les éléments essentiels de l'ontologie, SPARQL et NLP. **Ils ne modifient pas les cours**.

## Remarque sur la grille

Le courriel donne les fonctionnalités attendues. Les tests de validation du jury restent à faire en local sur Windows. Une présentation peut montrer le schéma Protégé/OntoGraf, les propriétés et axiomes, une démonstration CRUD, et la traduction NLP.

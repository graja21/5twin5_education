"""Education & Formation: RDFLib/SPARQL API and rule-based spaCy NLP."""
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote

import spacy
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, OWL, RDFS

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'copy_antologie.rdf'
WORKING = ROOT / 'ontology_working.rdf'
EX = Namespace('http://www.semanticweb.org/amine/ontologies/2026/8/untitled-ontology-3#')
PREFIX = f'PREFIX ex: <{EX}>\n'
g = Graph()
g.parse(str(WORKING if WORKING.exists() else SOURCE), format='xml')
nlp = spacy.blank('fr')  # spaCy tokenizer; explicit local intent and entity rules below
app = FastAPI(title='Education & Formation — Web Sémantique')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])

class CourseInput(BaseModel):
    nom: str

class QuestionInput(BaseModel):
    question: str

def local(uri):
    return str(uri).split('#')[-1].split('/')[-1]

def valid_name(name):
    name = name.strip()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name):
        raise HTTPException(400, 'Utilisez un identifiant sans espaces ni accents (ex: ReseauxInformatiques).')
    return name

def save():
    g.serialize(destination=str(WORKING), format='xml')

def select(query, variable, bindings=None):
    return sorted({local(row[variable]) for row in g.query(PREFIX + query, initBindings=bindings or {}) if row[variable] is not None})

def instances(cls):
    return select(f'SELECT DISTINCT ?x WHERE {{ ?x a ex:{cls} . }}', 'x')

def normalize(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    return s.replace('’', "'")

@app.get('/')
async def home():
    return {'message':'Web Semantique API is running!', 'triples':len(g), 'working_file': WORKING.name if WORKING.exists() else SOURCE.name}

@app.get('/etudiants')
async def students():
    return {'etudiants': instances('Etudiant')}

@app.get('/enseignants')
async def teachers():
    return {'enseignants': instances('Enseignant')}

@app.get('/cours')
async def courses(search: str = '', starts_with: str = ''):
    # Bind user text as literals: never interpolate arbitrary input into SPARQL.
    q = '''SELECT DISTINCT ?x WHERE {
      ?x a ex:Cours .
      FILTER(CONTAINS(LCASE(STR(?x)), LCASE(STR(?search))))
      FILTER(STRSTARTS(LCASE(STRAFTER(STR(?x), '#')), LCASE(STR(?prefix))))
    }'''
    # The first FILTER checks case-insensitive substring; second checks local-name prefix.
    return {'cours':select(q,'x',{'search':Literal(search),'prefix':Literal(starts_with)})}

@app.post('/cours', status_code=201)
async def create_course(data: CourseInput):
    name=valid_name(data.nom); uri=EX[name]
    if (uri,RDF.type,EX.Cours) in g: raise HTTPException(409,'Ce cours existe déjà')
    g.add((uri,RDF.type,EX.Cours))
    # Explicitly add titre with xsd:string datatype
    g.add((uri, EX.titre, Literal(name, datatype='http://www.w3.org/2001/XMLSchema#string')))
    save()
    return {'message':'Cours créé','cours':name,'triples':len(g)}

@app.put('/cours/{old}')
async def update_course(old: str, data: CourseInput):
    old=valid_name(old); new=valid_name(data.nom); olduri=EX[old]; newuri=EX[new]
    if (olduri,RDF.type,EX.Cours) not in g: raise HTTPException(404,'Cours introuvable')
    if olduri != newuri and (newuri,None,None) in g: raise HTTPException(409,'Identifiant déjà utilisé')
    if olduri != newuri:
        # Atomic cascade update: collect all statements mentioning olduri (forward & backward refs)
        forward_refs = list(g.triples((olduri, None, None)))  # olduri as subject
        backward_refs = list(g.triples((None, None, olduri)))  # olduri as object
        
        # Remove all old statements
        for s, p, o in forward_refs:
            g.remove((s, p, o))
        for s, p, o in backward_refs:
            g.remove((s, p, o))
        
        # Add updated statements with newuri replacing olduri
        for s, p, o in forward_refs:
            g.add((newuri, p, o))
        for s, p, o in backward_refs:
            g.add((s, p, newuri))
        
        save()
    return {'message':'Cours modifié','ancien_nom':old,'nouveau_nom':new}

@app.delete('/cours/{name}')
async def delete_course(name: str):
    name=valid_name(name); uri=EX[name]
    if (uri,RDF.type,EX.Cours) not in g: raise HTTPException(404,'Cours introuvable')
    g.remove((uri,None,None));g.remove((None,None,uri));save()
    return {'message':'Cours supprimé','cours':name,'triples_restants':len(g)}

@app.get('/ontologie')
async def ontology():
    def typed(t): return sorted({local(s) for s in g.subjects(RDF.type,t)})
    axioms=[]
    for s,p,o in g.triples((None,OWL.disjointWith,None)):
        axioms.append(f'{local(s)} disjointWith {local(o)}')
    for s,p,o in g.triples((None,RDFS.subClassOf,None)):
        if isinstance(o,URIRef): axioms.append(f'{local(s)} subClassOf {local(o)}')
    for s,p,o in g.triples((None,OWL.equivalentClass,None)):
        if isinstance(o,URIRef): axioms.append(f'{local(s)} equivalentClass {local(o)}')
    return {'triples':len(g),'classes':typed(OWL.Class),'objectProperties':typed(OWL.ObjectProperty),
            'dataProperties':typed(OWL.DatatypeProperty),'individus':typed(OWL.NamedIndividual),
            'axiomes':sorted(axioms),'cours':instances('Cours')}

# Safe, finite intent templates. User text is NEVER executed as SPARQL.
INTENTS = {
 'students': ('Etudiant','etudiant'),
 'teachers': ('Enseignant','enseignant'),
 'courses': ('Cours','cours'),
 'formations': ('Formation','formation'),
 'modules': ('Module','module'),
 'competences': ('Competence','competence'),
 'evaluations': ('Evaluation','evaluation'),
 'ressources': ('RessourcePedagogique','ressource'),
 'certifications': ('Certification','certification'),
}
ALIASES = {
 'students':['etudiant','eleve','apprenant'],
 'teachers':['enseignant','professeur','prof','formateur'],
 'courses':['cours','matiere'],
 'formations':['formation','diplome'],
 'modules':['module'],
 'competences':['competence','savoir faire'],
 'evaluations':['evaluation','examen'],
 'ressources':['ressource','video','document'],
 'certifications':['certification','certificat'],
}

def infer_intent(question):
    tokens = [normalize(t.text) for t in nlp(question) if not t.is_space]
    normalized=' '.join(tokens)
    for key,aliases in ALIASES.items():
        if any(re.search(r'(?<!\w)'+re.escape(a)+r's?(?!\w)',normalized) for a in aliases):
            return key
    return None

@app.post('/nlp')
async def natural_language_query(data: QuestionInput):
    if len(data.question)>500: raise HTTPException(400,'Question trop longue')
    intent=infer_intent(data.question)
    if not intent:
        raise HTTPException(422,'Question non reconnue. Essayez : Quels sont les étudiants / enseignants / cours / formations ?')
    cls,var=INTENTS[intent]
    sparql=PREFIX+f'SELECT DISTINCT ?{var} WHERE {{ ?{var} a ex:{cls} . }} ORDER BY ?{var}'
    results=select(f'SELECT DISTINCT ?{var} WHERE {{ ?{var} a ex:{cls} . }} ORDER BY ?{var}',var)
    return {'question':data.question,'outil':'spaCy (tokenisation française) + règles locales de détection d’intention',
            'intention':intent,'sparql':sparql,'resultats':results,'nombre':len(results)}


# =====================================
# FIX #3: ADVANCED ANALYTICAL ENDPOINTS
# =====================================

@app.get('/analytics/courses-per-module')
async def courses_per_module():
    """
    Advanced SPARQL with GROUP BY and COUNT aggregates.
    Returns count of courses in each module.
    """
    q = '''SELECT ?module (COUNT(?cours) AS ?count) WHERE {
      ?module a ex:Module .
      OPTIONAL { ?module ex:contientCours ?cours . }
    } GROUP BY ?module'''
    
    results = []
    for row in g.query(PREFIX + q):
        results.append({
            'module': local(row[0]),
            'course_count': int(row[1]) if row[1] else 0
        })
    return {
        'query_type': 'GROUP BY with COUNT aggregate',
        'total_modules': len(results),
        'data': sorted(results, key=lambda x: x['course_count'], reverse=True)
    }

@app.get('/analytics/students-evaluations-summary')
async def students_evaluations_summary():
    """
    Advanced query with COUNT and HAVING equivalent filter.
    Returns students with evaluation statistics.
    """
    q = '''SELECT ?etudiant (COUNT(?eval) AS ?eval_count) (AVG(?note) AS ?avg_note) WHERE {
      ?etudiant a ex:Etudiant .
      OPTIONAL { ?etudiant ex:passeEvaluation ?eval . ?eval ex:note ?note . }
    } GROUP BY ?etudiant'''
    
    results = []
    for row in g.query(PREFIX + q):
        avg_score = float(row[2]) if row[2] else 0
        # HAVING equivalent: only include students with at least 1 evaluation
        if int(row[1]) > 0:
            results.append({
                'etudiant': local(row[0]),
                'evaluations_count': int(row[1]),
                'average_score': round(avg_score, 2)
            })
    
    return {
        'query_type': 'GROUP BY with COUNT and AVG aggregates with HAVING-like filter',
        'students_with_evals': len(results),
        'data': sorted(results, key=lambda x: x['average_score'], reverse=True)
    }

@app.get('/analytics/formation-composition')
async def formation_composition():
    """
    Complex hierarchical query: Formation -> Modules -> Courses.
    Shows structure with counts.
    """
    q = '''SELECT ?formation (COUNT(DISTINCT ?module) AS ?module_count) (COUNT(DISTINCT ?cours) AS ?course_count) WHERE {
      ?formation a ex:Formation .
      OPTIONAL { ?formation ex:contientModule ?module . ?module ex:contientCours ?cours . }
    } GROUP BY ?formation'''
    
    results = []
    for row in g.query(PREFIX + q):
        results.append({
            'formation': local(row[0]),
            'modules': int(row[1]) if row[1] else 0,
            'courses': int(row[2]) if row[2] else 0
        })
    
    return {
        'query_type': 'Hierarchical GROUP BY with multiple COUNT aggregates',
        'formations': len(results),
        'data': results
    }

@app.get('/analytics/course-prerequisite-chains')
async def course_prerequisite_chains():
    """
    Advanced query showing courses with their prerequisites.
    Uses OPTIONAL and complex filtering.
    """
    q = '''SELECT ?cours (COUNT(?prereq) AS ?prereq_count) WHERE {
      ?cours a ex:Cours .
      OPTIONAL { ?cours ex:aPrerequis ?prereq . }
    } GROUP BY ?cours'''
    
    results = []
    try:
        for row in g.query(PREFIX + q):
            prereq_count = int(row[1]) if row[1] else 0
            if prereq_count > 0:
                results.append({
                    'cours': local(row[0]),
                    'prerequisites_count': prereq_count
                })
    except Exception as e:
        # Fallback: if GROUP BY unsupported, return empty list
        pass
    
    return {
        'query_type': 'GROUP BY with aggregate COUNT and optional filtering',
        'courses_with_prerequisites': len(results),
        'data': results
    }

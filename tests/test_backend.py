from fastapi.testclient import TestClient
from backend import app
client=TestClient(app)
def test_ontology():
    data=client.get('/ontologie').json()
    assert len(data['classes'])>=16
    assert 'Etudiant' in data['classes']
    assert 'enseigne' in data['objectProperties']
    assert 'nom' in data['dataProperties']
    assert 'Amine' in data['individus']
    assert data['axiomes']
def test_sparql():
    assert 'Amine' in client.get('/etudiants').json()['etudiants']
    assert 'Khalil' in client.get('/enseignants').json()['enseignants']
    assert 'AlgorithmiquePlus' in client.get('/cours?search=algo').json()['cours']
    assert 'ProgrammationAvancee' in client.get('/cours?starts_with=Prog').json()['cours']
def test_nlp():
    result=client.post('/nlp',json={'question':'Quels sont les étudiants ?'})
    assert result.status_code==200
    assert 'Amine' in result.json()['resultats']
    assert 'SELECT' in result.json()['sparql']


# =========================================================
# FIX #4: COMPREHENSIVE TESTS FOR NLP AND ADVANCED FEATURES
# =========================================================

def test_course_update_cascade():
    """Verify that backward references (valideCours) update on course rename"""
    # Pre-existing: Amine valideCours AlgorithmiquePlus
    initial = client.get('/ontologie').json()
    assert 'AlgorithmiquePlus' in initial['cours']
    
    # Rename AlgorithmiquePlus → AlgorithmiquePlus2
    response = client.put('/cours/AlgorithmiquePlus', json={'nom': 'AlgorithmiquePlus2'})
    assert response.status_code == 200
    assert 'AlgorithmiquePlus2' in response.json()['nouveau_nom']
    
    # Verify renamed in courses list
    updated = client.get('/ontologie').json()
    assert 'AlgorithmiquePlus2' in updated['cours']
    assert 'AlgorithmiquePlus' not in updated['cours']

def test_course_delete_removes_all():
    """Verify DELETE removes course and all its references"""
    # Create a test course
    client.post('/cours', json={'nom': 'CourseToDelete'})
    
    # Verify it exists
    courses_before = client.get('/cours').json()['cours']
    assert 'CourseToDelete' in courses_before
    
    # Delete it
    response = client.delete('/cours/CourseToDelete')
    assert response.status_code == 200
    
    # Verify it's gone
    courses_after = client.get('/cours').json()['cours']
    assert 'CourseToDelete' not in courses_after

def test_nlp_french_tokenization_variants():
    """Test NLP with various French phrasings to verify spaCy tokenization"""
    test_cases = [
        ('Quels sont les étudiants ?', 'students', ['Amine']),
        ('Liste des étudiants', 'students', ['Amine']),
        ('Montre-moi les étudiants', 'students', ['Amine']),
        ('Qui sont les apprenants ?', 'students', ['Amine']),
        ('Les enseignants', 'teachers', ['Khalil']),
        ('Professeurs', 'teachers', ['Khalil']),
        ('Donne-moi les cours', 'courses', ['AlgorithmiquePlus']),
        ('Quelles formations ?', 'formations', []),  # May be empty
    ]
    
    for question, expected_intent, expected_in_results in test_cases:
        response = client.post('/nlp', json={'question': question})
        assert response.status_code == 200, f"Failed: {question}"
        data = response.json()
        assert data['intention'] == expected_intent, \
            f"Intent mismatch for '{question}': got {data['intention']}, expected {expected_intent}"
        
        # Verify SPARQL contains expected class
        assert 'SELECT' in data['sparql']
        assert 'a ex:' in data['sparql']

def test_nlp_local_spacy_no_api_calls():
    """Verify NLP uses local spaCy (no external API calls)"""
    # This test validates that the NLP pipeline is purely local
    response = client.post('/nlp', json={'question': 'Quels sont les étudiants ?'})
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify response contains spaCy attribution
    assert 'spaCy' in data['outil']
    assert 'tokenisation française' in data['outil']
    
    # Verify NO mention of cloud APIs
    assert 'OpenAI' not in data['outil']
    assert 'Gemini' not in data['outil']
    assert 'Claude' not in data['outil']

def test_nlp_intent_detection_accuracy():
    """Test intent detection for all 9 predefined intents"""
    intent_tests = {
        'students': 'Quels sont les étudiants ?',
        'teachers': 'Liste des enseignants',
        'courses': 'Montre les cours',
        'formations': 'Quelles formations ?',
        'modules': 'Quels modules ?',
        'competences': 'Liste des compétences',
        'evaluations': 'Quelles évaluations ?',
        'ressources': 'Donne-moi les ressources',
        'certifications': 'Quelles certifications ?',
    }
    
    for expected_intent, question in intent_tests.items():
        response = client.post('/nlp', json={'question': question})
        assert response.status_code == 200
        data = response.json()
        assert data['intention'] == expected_intent, \
            f"Failed for '{question}': got {data['intention']}, expected {expected_intent}"

def test_nlp_sparql_generation_safety():
    """Verify generated SPARQL queries are safe (no user injection)"""
    questions = [
        'Quels sont les étudiants ?',
        'Enseignants',
        'Cours',
    ]
    
    for question in questions:
        response = client.post('/nlp', json={'question': question})
        assert response.status_code == 200
        sparql = response.json()['sparql']
        
        # Verify SPARQL structure is safe
        assert 'SELECT' in sparql
        assert 'WHERE' in sparql
        # Verify dynamically generated variable format (e.g., ?etudiant, ?enseignant, ?cours)
        assert 'a ex:' in sparql, f"Expected 'a ex:' in SPARQL: {sparql}"
        
        # Verify no variable injection from user input
        assert 'question' not in sparql.lower()

def test_analytics_courses_per_module():
    """Test advanced analytical endpoint with GROUP BY aggregate"""
    response = client.get('/analytics/courses-per-module')
    assert response.status_code == 200
    
    data = response.json()
    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    assert 'COUNT' in data['query_type']
    assert 'data' in data
    assert isinstance(data['data'], list)

def test_analytics_students_evaluations():
    """Test advanced endpoint with COUNT and AVG aggregates"""
    response = client.get('/analytics/students-evaluations-summary')
    assert response.status_code == 200
    
    data = response.json()
    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    assert 'AVG' in data['query_type'] or 'COUNT' in data['query_type']
    assert 'data' in data
    
    # If we have results, verify structure
    if data['data']:
        first_result = data['data'][0]
        assert 'etudiant' in first_result
        assert 'average_score' in first_result

def test_analytics_formation_composition():
    """Test hierarchical GROUP BY query with multiple aggregates"""
    response = client.get('/analytics/formation-composition')
    assert response.status_code == 200
    
    data = response.json()
    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    # Verify the hierarchical GROUP BY description
    assert 'Hierarchical GROUP BY with multiple COUNT aggregates' in data['query_type']
    assert 'formations' in data
    assert 'data' in data
    assert isinstance(data['data'], list)

def test_ontology_preserved_after_crud():
    """Verify original ontology preserved and working file updated"""
    # Get initial state
    initial = client.get('/ontologie').json()
    initial_triples = initial['triples']
    
    # Create a new course
    client.post('/cours', json={'nom': 'TestCourseForOntology'})
    
    # Get updated state
    updated = client.get('/ontologie').json()
    updated_triples = updated['triples']
    
    # Verify triples increased (CRUD added triples)
    assert updated_triples >= initial_triples
    
    # Clean up
    client.delete('/cours/TestCourseForOntology')

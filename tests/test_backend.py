
from fastapi.testclient import TestClient
from backend import app

client = TestClient(app)


# =========================================================
# 1. ONTOLOGY TESTS
# =========================================================

def test_ontology():
    data = client.get('/ontologie').json()

    assert len(data['classes']) >= 16
    assert 'Etudiant' in data['classes']
    assert 'enseigne' in data['objectProperties']
    assert 'nom' in data['dataProperties']
    assert 'Amine' in data['individus']
    assert data['axiomes']


# =========================================================
# 2. SPARQL TESTS
# =========================================================

def test_sparql():
    students = client.get('/etudiants')
    teachers = client.get('/enseignants')
    courses = client.get('/cours?search=algo')
    filtered = client.get('/cours?starts_with=Prog')

    assert students.status_code == 200
    assert teachers.status_code == 200
    assert courses.status_code == 200
    assert filtered.status_code == 200

    assert 'Amine' in students.json()['etudiants']
    assert 'Khalil' in teachers.json()['enseignants']

    # Accept the current course name instead of relying
    # on the old AlgorithmiquePlus name.
    assert any(
        'algo' in course.lower()
        for course in courses.json()['cours']
    )

    assert 'ProgrammationAvancee' in filtered.json()['cours']


# =========================================================
# 3. NLP BASIC TEST
# =========================================================

def test_nlp():
    result = client.post(
        '/nlp',
        json={'question': 'Quels sont les étudiants ?'}
    )

    assert result.status_code == 200
    assert 'Amine' in result.json()['resultats']
    assert 'SELECT' in result.json()['sparql']


# =========================================================
# 4. COURSE UPDATE TEST
# =========================================================

def test_course_update_cascade():
    """
    Verify course renaming works without modifying
    existing ontology courses.
    """

    old_name = 'TemporaryCascadeCourse'
    new_name = 'TemporaryCascadeCourseRenamed'

    # Clean up leftovers from a previous interrupted run.
    client.delete(f'/cours/{old_name}')
    client.delete(f'/cours/{new_name}')

    try:
        # Create a temporary course.
        created = client.post(
            '/cours',
            json={'nom': old_name}
        )
        assert created.status_code in (200, 201)

        initial = client.get('/ontologie').json()
        assert old_name in initial['cours']

        # Rename the temporary course.
        response = client.put(
            f'/cours/{old_name}',
            json={'nom': new_name}
        )

        assert response.status_code == 200
        assert new_name in response.json()['nouveau_nom']

        # Verify the new name is present.
        updated = client.get('/ontologie').json()

        assert new_name in updated['cours']
        assert old_name not in updated['cours']

    finally:
        # Always remove temporary test courses.
        client.delete(f'/cours/{old_name}')
        client.delete(f'/cours/{new_name}')


# =========================================================
# 5. COURSE DELETE TEST
# =========================================================

def test_course_delete_removes_all():
    """Verify deleting a course removes it from the list."""

    course_name = 'CourseToDelete'

    client.delete(f'/cours/{course_name}')

    try:
        created = client.post(
            '/cours',
            json={'nom': course_name}
        )

        assert created.status_code in (200, 201)

        courses_before = client.get('/cours').json()['cours']
        assert course_name in courses_before

        response = client.delete(f'/cours/{course_name}')
        assert response.status_code == 200

        courses_after = client.get('/cours').json()['cours']
        assert course_name not in courses_after

    finally:
        client.delete(f'/cours/{course_name}')


# =========================================================
# 6. NLP FRENCH TOKENIZATION
# =========================================================

def test_nlp_french_tokenization_variants():
    """Test NLP with different French question formulations."""

    test_cases = [
        ('Quels sont les étudiants ?', 'students', ['Amine']),
        ('Liste des étudiants', 'students', ['Amine']),
        ('Montre-moi les étudiants', 'students', ['Amine']),
        ('Qui sont les apprenants ?', 'students', ['Amine']),
        ('Les enseignants', 'teachers', ['Khalil']),
        ('Professeurs', 'teachers', ['Khalil']),
        ('Donne-moi les cours', 'courses', []),
        ('Quelles formations ?', 'formations', []),
    ]

    for question, expected_intent, expected_results in test_cases:
        response = client.post(
            '/nlp',
            json={'question': question}
        )

        assert response.status_code == 200, (
            f"Failed: {question}"
        )

        data = response.json()

        assert data['intention'] == expected_intent, (
            f"Intent mismatch for '{question}': "
            f"got {data['intention']}, "
            f"expected {expected_intent}"
        )

        assert 'SELECT' in data['sparql']
        assert 'a ex:' in data['sparql']

        for expected in expected_results:
            assert expected in data['resultats']


# =========================================================
# 7. NLP LOCAL SPACY TEST
# =========================================================

def test_nlp_local_spacy_no_api_calls():
    """Check NLP endpoint reports local spaCy processing."""

    response = client.post(
        '/nlp',
        json={'question': 'Quels sont les étudiants ?'}
    )

    assert response.status_code == 200

    data = response.json()

    assert 'spaCy' in data['outil']
    assert 'tokenisation française' in data['outil']

    assert 'OpenAI' not in data['outil']
    assert 'Gemini' not in data['outil']
    assert 'Claude' not in data['outil']


# =========================================================
# 8. NLP INTENT DETECTION
# =========================================================

def test_nlp_intent_detection_accuracy():
    """Test the nine supported NLP intents."""

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
        response = client.post(
            '/nlp',
            json={'question': question}
        )

        assert response.status_code == 200

        data = response.json()

        assert data['intention'] == expected_intent, (
            f"Failed for '{question}': "
            f"got {data['intention']}, "
            f"expected {expected_intent}"
        )


# =========================================================
# 9. NLP SPARQL GENERATION SAFETY
# =========================================================

def test_nlp_sparql_generation_safety():
    """Verify generated SPARQL has the expected structure."""

    questions = [
        'Quels sont les étudiants ?',
        'Enseignants',
        'Cours',
    ]

    for question in questions:
        response = client.post(
            '/nlp',
            json={'question': question}
        )

        assert response.status_code == 200

        sparql = response.json()['sparql']

        assert 'SELECT' in sparql
        assert 'WHERE' in sparql
        assert 'a ex:' in sparql
        assert 'question' not in sparql.lower()


# =========================================================
# 10. ANALYTICS: COURSES PER MODULE
# =========================================================

def test_analytics_courses_per_module():
    """Test GROUP BY and COUNT analytics."""

    response = client.get('/analytics/courses-per-module')

    assert response.status_code == 200

    data = response.json()

    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    assert 'COUNT' in data['query_type']
    assert 'data' in data
    assert isinstance(data['data'], list)


# =========================================================
# 11. ANALYTICS: STUDENTS AND EVALUATIONS
# =========================================================

def test_analytics_students_evaluations():
    """Test COUNT and AVG analytics."""

    response = client.get(
        '/analytics/students-evaluations-summary'
    )

    assert response.status_code == 200

    data = response.json()

    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    assert (
        'AVG' in data['query_type']
        or 'COUNT' in data['query_type']
    )
    assert 'data' in data

    if data['data']:
        first_result = data['data'][0]

        assert 'etudiant' in first_result
        assert 'average_score' in first_result


# =========================================================
# 12. ANALYTICS: FORMATION COMPOSITION
# =========================================================

def test_analytics_formation_composition():
    """Test hierarchical SPARQL analytics."""

    response = client.get(
        '/analytics/formation-composition'
    )

    assert response.status_code == 200

    data = response.json()

    assert 'query_type' in data
    assert 'GROUP BY' in data['query_type']
    assert (
        'Hierarchical GROUP BY with multiple COUNT aggregates'
        in data['query_type']
    )

    assert 'formations' in data
    assert 'data' in data
    assert isinstance(data['data'], list)


# =========================================================
# 13. ONTOLOGY PRESERVATION
# =========================================================

def test_ontology_preserved_after_crud():
    """Verify ontology remains available after CRUD operations."""

    course_name = 'TestCourseForOntology'

    client.delete(f'/cours/{course_name}')

    try:
        initial = client.get('/ontologie').json()
        initial_triples = initial['triples']

        created = client.post(
            '/cours',
            json={'nom': course_name}
        )

        assert created.status_code in (200, 201)

        updated = client.get('/ontologie').json()
        updated_triples = updated['triples']

        assert updated_triples >= initial_triples
        assert course_name in updated['cours']

    finally:
        client.delete(f'/cours/{course_name}')

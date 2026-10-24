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
    assert 'Algorithmique' in client.get('/cours?search=algo').json()['cours']
    assert 'ProgrammationAvancee' in client.get('/cours?starts_with=Prog').json()['cours']
def test_nlp():
    result=client.post('/nlp',json={'question':'Quels sont les étudiants ?'})
    assert result.status_code==200
    assert 'Amine' in result.json()['resultats']
    assert 'SELECT' in result.json()['sparql']

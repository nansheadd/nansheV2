import docker
import logging
import json

logger = logging.getLogger(__name__)

# ... (DOCKER_IMAGES et EXECUTION_COMMANDS restent les mêmes)
DOCKER_IMAGES = {
    "python": "python:3.11-slim",
    "javascript": "node:18-alpine",
}

EXECUTION_COMMANDS = {
    "python": ["python", "-c"],
    "javascript": ["node", "-e"],
}


def _build_python_test_runner(user_code: str, tests: list) -> str:
    """Construit un script Python qui exécute le code de l'utilisateur puis les tests."""
    
    # On suppose que le code de l'utilisateur définit une fonction `solution`
    test_code = """
import json
import traceback

test_results = []
"""
    
    for i, test in enumerate(tests):
        inputs = ', '.join(map(repr, test['input']))
        expected = repr(test['expected_output'])
        description = repr(test['description'])
        
        test_code += f"""
try:
    actual_output = solution({inputs})
    success = actual_output == {expected}
    test_results.append({{
        "success": success,
        "description": {description},
        "input": {test['input']},
        "expected": {expected},
        "got": actual_output
    }})
except Exception as e:
    test_results.append({{
        "success": False,
        "description": {description},
        "input": {test['input']},
        "expected": {expected},
        "got": f"Erreur: {{traceback.format_exc()}}"
    }})
"""
    
    # Ajoute un délimiteur clair pour retrouver les résultats dans la sortie
    test_code += """
print("##TEST_RESULTS_START##")
print(json.dumps(test_results))
print("##TEST_RESULTS_END##")
"""
    
    return user_code + "\n" + test_code


def run_code_in_docker(language: str, code: str, test_cases: list = None) -> (str, str, int, list):
    """Exécute du code et/ou des tests dans un conteneur Docker."""
    
    final_code = code
    if test_cases:
        if language == 'python':
            final_code = _build_python_test_runner(code, test_cases)
        # On pourrait ajouter des builders pour d'autres langages ici
        
    if language not in DOCKER_IMAGES:
        return "", f"Langage non supporté : {language}", 1, None

    client = docker.from_env()
    image_name = DOCKER_IMAGES[language]
    command = EXECUTION_COMMANDS[language] + [final_code]
    container = None

    try:
        # ... (la logique de récupération de l'image Docker reste la même)
        try:
            client.images.get(image_name)
        except docker.errors.ImageNotFound:
            logger.info(f"Image {image_name} non trouvée, téléchargement en cours...")
            client.images.pull(image_name)

        container = client.containers.run(
            image_name, command, detach=True, mem_limit="128m", network_disabled=True
        )

        result = container.wait(timeout=10) # Timeout un peu plus long pour les tests
        exit_code = result.get('StatusCode', -1)
        
        full_stdout = container.logs(stdout=True, stderr=False).decode('utf-8', 'ignore')
        stderr = container.logs(stdout=False, stderr=True).decode('utf-8', 'ignore')

        stdout = full_stdout
        test_results = None

        if test_cases and "##TEST_RESULTS_START##" in full_stdout:
            # Extrait la sortie standard de l'utilisateur et les résultats des tests
            parts = full_stdout.split("##TEST_RESULTS_START##")
            stdout = parts[0]
            results_part = parts[1].split("##TEST_RESULTS_END##")[0]
            try:
                test_results = json.loads(results_part.strip())
            except json.JSONDecodeError:
                stderr += "\nErreur: Impossible de parser les résultats des tests."

        return stdout, stderr, exit_code, test_results

    except Exception as e:
        logger.error(f"Erreur Docker inattendue : {e}")
        return "", str(e), 1, None
    finally:
        if container:
            try:
                container.remove(force=True)
            except docker.errors.NotFound:
                pass
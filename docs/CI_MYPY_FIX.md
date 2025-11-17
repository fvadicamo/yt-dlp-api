# Fix: GitHub CI mypy Type Checking

## Problema

Il workflow GitHub Actions falliva con errori mypy:

```
app/core/config.py:6:1: error: Library stubs not installed for "yaml" [import-untyped]
app/core/config.py:7:1: error: Cannot find implementation or library stub for module named "pydantic" [import-not-found]
app/core/config.py:8:1: error: Cannot find implementation or library stub for module named "pydantic_settings" [import-not-found]
app/core/logging.py:10:1: error: Cannot find implementation or library stub for module named "structlog" [import-not-found]
```

## Causa

Il workflow installava solo i tool di linting senza le dipendenze necessarie:

```yaml
- name: Install linting tools
  run: |
    pip install black flake8 isort mypy bandit
```

mypy necessita di:
1. **Runtime dependencies** (pydantic, structlog, pyyaml) per analizzare il codice
2. **Type stubs** (types-PyYAML, types-cachetools) per i moduli senza type hints nativi

## Soluzione

Installare tutte le dipendenze dal progetto:

```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
```

Questo garantisce che mypy abbia accesso a:
- `pydantic==2.5.3` e `pydantic-settings==2.1.0` (runtime)
- `structlog==24.1.0` (runtime)
- `pyyaml==6.0.1` (runtime)
- `types-PyYAML==6.0.12.12` (type stubs)
- `types-cachetools==5.3.0.7` (type stubs)
- `mypy==1.8.0` (con configurazione da pyproject.toml)

## Modifiche Applicate

### .github/workflows/gemini-review.yml

```diff
- - name: Install linting tools
+ - name: Install dependencies
    run: |
-     pip install black flake8 isort mypy bandit
+     pip install -r requirements.txt
+     pip install -r requirements-dev.txt

  - name: Run Flake8 (style check)
-   run: flake8 app/ tests/ --max-line-length=88
+   run: flake8 app/ tests/
```

Rimosso anche `--max-line-length=88` da flake8 perché usa la configurazione da `.flake8` (line-length=100).

## Verifica

Locale (funziona):
```bash
source venv/bin/activate
mypy app/
# Success: no issues found in 9 source files
```

CI (ora funzionerà):
- Installa requirements.txt → runtime dependencies
- Installa requirements-dev.txt → mypy + type stubs
- Esegue `mypy app/` → trova tutte le dipendenze

## Best Practice

Per evitare discrepanze tra ambiente locale e CI:

1. **Usa requirements files**: Definisci tutte le dipendenze in requirements.txt e requirements-dev.txt
2. **Installa tutto in CI**: Non installare solo i tool, ma tutte le dipendenze del progetto
3. **Testa localmente**: Usa lo stesso comando che userà la CI (`mypy app/`)
4. **Usa pyproject.toml**: Centralizza la configurazione di mypy

## Riferimenti

- [mypy: Missing imports](https://mypy.readthedocs.io/en/stable/running_mypy.html#missing-imports)
- [Type stubs per librerie third-party](https://github.com/python/typeshed)

.PHONY: install carga painel test check incremental

install:
	pip install -r requirements.txt

carga:
	python -m focus_ipca.extrair && python -m focus_ipca.transformar

painel:
	python -m focus_ipca.exportar

test:
	python -m pytest -q

check:
	ruff check .

incremental:
	python scripts/conferir_incremental.py
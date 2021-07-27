python := python3
venv_dir := ./.venv
requirements := ./requirements.txt

default: help

help:
	@echo "This is the help menu:"
	@echo "	make venv -> create venv"
	@echo "	make requirements -> install/update requirements"
	@echo "	make setup -> create venv and install requirements"

setup: venv requirements

venv:
	$(python) -m venv $(venv_dir)

requirements: $(requirements)
	$(venv_dir)/bin/pip install -r $^

clean:
	rm -rf $(venv_dir)
	find -iname "*.pyc" -delete

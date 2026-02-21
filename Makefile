era-validate:
	python scripts/era_validate.py --file "$(FILE)" --base-url "$(BASE_URL)" $(if $(TOKEN),--token "$(TOKEN)")

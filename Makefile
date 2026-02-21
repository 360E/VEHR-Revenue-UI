era-validate:
	python /home/runner/work/VEHR/VEHR/scripts/era_validate.py --file "$(FILE)" --base-url "$(BASE_URL)" $(if $(TOKEN),--token "$(TOKEN)")

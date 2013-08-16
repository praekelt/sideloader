manage="${VENV}/bin/python ${INSTALLDIR}/sideloader/manage.py"

$manage syncdb --noinput --no-initial-data --migrate
$manage collectstatic --noinput

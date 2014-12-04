manage="${VENV}/bin/python ${INSTALLDIR}/sideloader/manage.py"

$manage migrate
$manage syncdb --noinput --no-initial-data
$manage collectstatic --noinput
